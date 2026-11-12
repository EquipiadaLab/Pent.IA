"""Implementacao de EventSink + coordenacao de campanha (Trilho B).

Entrega ao Trilho A (o Motor):
- ``SQLiteEventSink`` implementando ``app.interfaces.EventSink``;
- a fila de aprovacao (``wait_approval`` bloqueia ate um humano decidir);
- ``should_stop()`` consultavel (parada de emergencia).

O Motor chama ``sink.emit / audit / should_stop / wait_approval``. A API
chama o ``Coordinator`` para resolver aprovacoes e pedir parada.

Garantias da fila de aprovacao:
- o pedido fica "aprovavel" assim que o lance aparece como ``pending``
  (sem 409 por clicar cedo);
- exatamente UM ``approval_requested`` e UM ``approval_resolved`` por lance,
  ambos com ``move`` e ``data.move`` (o resolved traz ``approval`` e ``actor``);
- a decisao e gravada ANTES de o Motor continuar, entao nunca sobrescreve o
  resultado do teste.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.audit import AuditTrail, mask_evidence
from app.db import Database
from app.interfaces import EventSink
from app.models import (
    Approval,
    AuditEntry,
    CampaignState,
    Event,
    EventType,
    Move,
    Score,
)

STOP_ACTOR = "parada de emergencia"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalNotPending(Exception):
    """Tentativa de resolver uma aprovacao que nao esta pendente."""


class Coordinator:
    """Estado em memoria compartilhado entre API e sinks.

    Mantem, por campanha: um evento de parada e as aprovacoes pendentes
    (futuros aguardados por ``wait_approval``). Sobrevive enquanto o
    processo vive; o estado duravel fica no SQLite.
    """

    def __init__(self, db: Database) -> None:
        self.db = db
        self.audit = AuditTrail(db)
        self._stop: dict[str, asyncio.Event] = {}
        self._pending: dict[tuple[str, int], asyncio.Future[Approval]] = {}
        self._actors: dict[tuple[str, int], str] = {}
        self._lock = asyncio.Lock()

    # ---- parada de emergencia -------------------------------------------
    def _stop_event(self, campaign_id: str) -> asyncio.Event:
        ev = self._stop.get(campaign_id)
        if ev is None:
            ev = asyncio.Event()
            self._stop[campaign_id] = ev
        return ev

    def is_stop_requested(self, campaign_id: str) -> bool:
        ev = self._stop.get(campaign_id)
        return ev is not None and ev.is_set()

    async def request_stop(self, campaign_id: str, actor: str = "operator") -> None:
        self._stop_event(campaign_id).set()
        await self.db.append_event(
            Event(
                campaign_id=campaign_id,
                type=EventType.STOP_REQUESTED,
                at=_utcnow(),
                data={"actor": actor},
            )
        )
        await self.db.set_state(campaign_id, CampaignState.STOPPED, finished=True)
        # Libera quem estiver aguardando aprovacao: parada vence tudo.
        async with self._lock:
            for (cid, move_no), fut in list(self._pending.items()):
                if cid == campaign_id and not fut.done():
                    self._actors[(cid, move_no)] = STOP_ACTOR
                    fut.set_result(Approval.DENIED)

    # ---- aprovacao ------------------------------------------------------
    def new_sink(self, campaign_id: str) -> "SQLiteEventSink":
        return SQLiteEventSink(self, campaign_id)

    async def _register_approval(
        self, campaign_id: str, move_no: int
    ) -> asyncio.Future[Approval]:
        """Devolve o futuro do lance (cria se nao existir). Um futuro ja
        resolvido e devolvido como esta: a decisao antecipada vale."""
        async with self._lock:
            key = (campaign_id, move_no)
            fut = self._pending.get(key)
            if fut is None:
                fut = asyncio.get_running_loop().create_future()
                if self.is_stop_requested(campaign_id):
                    self._actors[key] = STOP_ACTOR
                    fut.set_result(Approval.DENIED)
                self._pending[key] = fut
            return fut

    def actor_for(self, campaign_id: str, move_no: int) -> str | None:
        return self._actors.get((campaign_id, move_no))

    def pending_moves(self, campaign_id: str) -> list[int]:
        return sorted(
            move_no
            for (cid, move_no), fut in self._pending.items()
            if cid == campaign_id and not fut.done()
        )

    async def resolve_approval(
        self, campaign_id: str, move_no: int, approved: bool, actor: str
    ) -> Approval:
        """Registra a decisao humana. O evento ``approval_resolved`` e o
        lance atualizado sao gravados pelo sink da campanha."""
        async with self._lock:
            fut = self._pending.get((campaign_id, move_no))
            if fut is None or fut.done():
                raise ApprovalNotPending(
                    f"Lance {move_no} da campanha {campaign_id} nao esta aguardando aprovacao."
                )
            decision = Approval.APPROVED if approved else Approval.DENIED
            self._actors[(campaign_id, move_no)] = actor
            fut.set_result(decision)
        return decision


class SQLiteEventSink(EventSink):
    """Grava eventos no SQLite e coordena parada/aprovacao."""

    def __init__(self, coordinator: Coordinator, campaign_id: str) -> None:
        self._co = coordinator
        self._db = coordinator.db
        self.campaign_id = campaign_id
        self._requested: set[int] = set()
        self._resolved: set[int] = set()

    async def emit(self, event: Event) -> None:
        if event.campaign_id != self.campaign_id:
            event = event.model_copy(update={"campaign_id": self.campaign_id})
        if event.move is not None:
            event = event.model_copy(update={"move": _sanitize_move(event.move)})
            if event.move.approval is Approval.PENDING:
                # Aprovavel desde ja: evita 409 se o humano clicar cedo.
                await self._co._register_approval(self.campaign_id, event.move.move)

        move_no = _move_no(event)
        if event.type is EventType.APPROVAL_REQUESTED and move_no is not None:
            if move_no in self._requested:
                return  # dedup
            self._requested.add(move_no)
            event = event.model_copy(update={"data": {**event.data, "move": move_no}})
        if event.type is EventType.APPROVAL_RESOLVED and move_no is not None:
            if move_no in self._resolved:
                return  # dedup: o sink ja publicou ao receber a decisao
            self._resolved.add(move_no)

        await self._db.append_event(event)  # atribui seq

        if event.move is not None:
            await self._db.upsert_move(self.campaign_id, event.move)

        await self._apply_state(event)

    async def audit(self, entry: AuditEntry) -> None:
        if entry.campaign_id != self.campaign_id:
            entry = entry.model_copy(update={"campaign_id": self.campaign_id})
        await self._co.audit.record(entry)  # mascara antes de gravar

    async def should_stop(self) -> bool:
        return self._co.is_stop_requested(self.campaign_id)

    async def wait_approval(self, campaign_id: str, move: Move) -> Approval:
        pending = _sanitize_move(move.model_copy(update={"approval": Approval.PENDING}))
        fut = await self._co._register_approval(self.campaign_id, move.move)
        if move.move not in self._requested:  # runners que nao emitem o pedido
            await self.emit(
                Event(
                    campaign_id=self.campaign_id,
                    type=EventType.APPROVAL_REQUESTED,
                    at=_utcnow(),
                    move=pending,
                    data={"move": move.move},
                )
            )

        decision = await fut

        # Grava a decisao ANTES de devolver ao Motor (nao sobrescreve resultado).
        decided = pending.model_copy(update={"approval": decision})
        actor = self._co.actor_for(self.campaign_id, move.move) or "operator"
        await self.emit(
            Event(
                campaign_id=self.campaign_id,
                type=EventType.APPROVAL_RESOLVED,
                at=_utcnow(),
                move=decided,
                data={"move": move.move, "approval": decision.value, "actor": actor},
            )
        )
        if not self._co.is_stop_requested(self.campaign_id):
            await self._db.set_state(self.campaign_id, CampaignState.RUNNING)
        return decision

    async def _apply_state(self, event: Event) -> None:
        t = event.type
        if t is EventType.CAMPAIGN_STARTED:
            await self._db.set_state(self.campaign_id, CampaignState.RUNNING)
        elif t is EventType.APPROVAL_REQUESTED:
            if not self._co.is_stop_requested(self.campaign_id):
                await self._db.set_state(self.campaign_id, CampaignState.WAITING_APPROVAL)
        elif t is EventType.SCORE_UPDATED and "score" in event.data:
            await self._db.set_score(
                self.campaign_id, Score.model_validate(event.data["score"])
            )
        elif t is EventType.CAMPAIGN_FINISHED:
            if self._co.is_stop_requested(self.campaign_id):
                return
            final = {
                "failed": CampaignState.FAILED,
                "stopped": CampaignState.STOPPED,
            }.get(str(event.data.get("state", "")), CampaignState.FINISHED)
            await self._db.set_state(self.campaign_id, final, finished=True)


def _move_no(event: Event) -> int | None:
    if event.move is not None:
        return event.move.move
    value = event.data.get("move")
    return value if isinstance(value, int) else None


def _sanitize_move(move: Move) -> Move:
    """Remascara evidencias do lance (defesa em profundidade)."""
    if not move.evidence:
        return move
    return move.model_copy(
        update={"evidence": [mask_evidence(ev) for ev in move.evidence]}
    )

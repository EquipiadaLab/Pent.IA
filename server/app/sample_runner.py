"""run_campaign FALSO da Plataforma (Trilho B).

NAO e o motor. Vive fora de ``app/engine/`` (que e do Trilho A). Serve para:
- testar a API/sink ponta a ponta sem depender do motor real;
- alimentar o frontend com uma partida de exemplo para desenhar a UI.

Quando ``app.engine.runner.run_campaign`` existir, a aplicacao usa o real;
caso contrario cai neste fake (ver ``app/main.py``). A assinatura segue o
contrato ``CampaignRunner``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from app.interfaces import EventSink
from app.models import (
    Approval,
    AuditEntry,
    Campaign,
    CampaignConfig,
    CampaignState,
    Confidence,
    Event,
    EventType,
    Evidence,
    Grade,
    Move,
    Phase,
    Profile,
    Score,
    Severity,
    Status,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sample_moves() -> list[Move]:
    return [
        Move(
            move=1,
            test_id="TLS-001",
            title="Redirecionamento HTTP->HTTPS",
            phase=Phase.OPENING,
            profile=Profile.PASSIVE,
            wstg="WSTG-CONF-07",
            status=Status.PASS,
            severity=Severity.LOW,
            grade=Grade.BEST,
            confidence=Confidence.HIGH,
            evidence=[
                Evidence(
                    id="ev-1-1",
                    request="GET / HTTP/1.1",
                    response_status=301,
                    response_headers={"location": "https://alvo.exemplo/"},
                )
            ],
        ),
        Move(
            move=2,
            test_id="HDR-002",
            title="Cabecalhos de seguranca ausentes",
            phase=Phase.MIDDLEGAME,
            profile=Profile.PASSIVE,
            wstg="WSTG-CONF-12",
            owasp_top10="A05:2021",
            status=Status.FAIL,
            severity=Severity.MEDIUM,
            grade=Grade.MISTAKE,
            confidence=Confidence.HIGH,
            evidence=[
                Evidence(
                    id="ev-2-1",
                    request="GET / HTTP/1.1",
                    response_status=200,
                    response_headers={"server": "nginx"},
                    note="Sem Content-Security-Policy nem X-Frame-Options.",
                )
            ],
        ),
        Move(
            move=3,
            test_id="COOKIE-001",
            title="Flags de cookie de sessao",
            phase=Phase.MIDDLEGAME,
            profile=Profile.PASSIVE,
            wstg="WSTG-SESS-02",
            owasp_top10="A07:2025",
            status=Status.WARNING,
            severity=Severity.MEDIUM,
            grade=Grade.INACCURACY,
            confidence=Confidence.HIGH,
            evidence=[
                Evidence(
                    id="ev-3-1",
                    request="GET / HTTP/1.1",
                    response_status=200,
                    response_headers={"set-cookie": "sid=segredo-super-secreto; HttpOnly"},
                )
            ],
        ),
    ]


_ENDGAME_MOVE = Move(
    move=4,
    test_id="CONF-004",
    title="Arquivo /.git/HEAD exposto",
    phase=Phase.ENDGAME,
    profile=Profile.ACTIVE_LIGHT,
    wstg="WSTG-CONF-05",
    approval=Approval.PENDING,
)


def _score(moves: list[Move]) -> Score:
    counts: dict[Grade, int] = {}
    for m in moves:
        if m.grade:
            counts[m.grade] = counts.get(m.grade, 0) + 1
    return Score(accuracy=72.5, eval_bar=-15.0, counts=counts)


async def run_campaign(
    campaign_id: str, config: CampaignConfig, sink: EventSink
) -> Campaign:
    """Emite uma partida de exemplo respeitando parada e aprovacao."""
    await sink.emit(
        Event(campaign_id=campaign_id, type=EventType.CAMPAIGN_STARTED, at=_now())
    )

    played: list[Move] = []
    for move in _sample_moves():
        if await sink.should_stop():
            break
        await sink.emit(
            Event(
                campaign_id=campaign_id,
                type=EventType.TEST_STARTED,
                at=_now(),
                move=move.model_copy(update={"started_at": _now()}),
            )
        )
        await asyncio.sleep(0)  # cede o loop (simula I/O)
        await sink.audit(
            AuditEntry(
                campaign_id=campaign_id,
                at=_now(),
                method="GET",
                url=config.origin,
                allowed=True,
                status_code=move.evidence[0].response_status if move.evidence else None,
            )
        )
        finished = move.model_copy(update={"finished_at": _now()})
        await sink.emit(
            Event(
                campaign_id=campaign_id,
                type=EventType.FINDING_CREATED,
                at=_now(),
                move=finished,
            )
        )
        played.append(finished)
        await sink.emit(
            Event(
                campaign_id=campaign_id,
                type=EventType.SCORE_UPDATED,
                at=_now(),
                data={"score": _score(played).model_dump(mode="json")},
            )
        )

    # Lance de endgame exige aprovacao humana.
    if not await sink.should_stop():
        decision = await sink.wait_approval(campaign_id, _ENDGAME_MOVE)
        resolved = _ENDGAME_MOVE.model_copy(update={"approval": decision})
        if decision is Approval.APPROVED:
            resolved = resolved.model_copy(
                update={
                    "status": Status.FAIL,
                    "severity": Severity.HIGH,
                    "grade": Grade.BLUNDER,
                    "confidence": Confidence.HIGH,
                    "started_at": _now(),
                    "finished_at": _now(),
                    "evidence": [
                        Evidence(
                            id="ev-4-1",
                            request="GET /.git/HEAD HTTP/1.1",
                            response_status=200,
                            note="Repositorio Git exposto.",
                        )
                    ],
                }
            )
            await sink.audit(
                AuditEntry(
                    campaign_id=campaign_id,
                    at=_now(),
                    method="GET",
                    url=config.origin + "/.git/HEAD",
                    allowed=True,
                    status_code=200,
                    actor="agent",
                )
            )
        await sink.emit(
            Event(
                campaign_id=campaign_id,
                type=EventType.FINDING_CREATED,
                at=_now(),
                move=resolved,
            )
        )
        played.append(resolved)

    await sink.emit(
        Event(
            campaign_id=campaign_id,
            type=EventType.SCORE_UPDATED,
            at=_now(),
            data={"score": _score(played).model_dump(mode="json")},
        )
    )
    await sink.emit(
        Event(campaign_id=campaign_id, type=EventType.CAMPAIGN_FINISHED, at=_now())
    )

    return Campaign(
        id=campaign_id,
        config=config,
        state=CampaignState.FINISHED,
        created_at=_now(),
        finished_at=_now(),
        score=_score(played),
        moves=played,
    )

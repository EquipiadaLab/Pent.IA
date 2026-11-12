"""Item 8: trilha de auditoria cronologica unica (caminho NOVO, aditivo).

GET /campaigns/{id}/audit -> list[TimelineEntry] em JSON, juntando:
  decisoes/hipoteses do agente, pedidos e decisoes de aprovacao, comandos
  (cada requisicao HTTP, permitida ou bloqueada), resultados e parada.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.context import AppContext, get_ctx
from app.models import AuditEntry, Event, EventType, TimelineEntry

router = APIRouter()


@router.get("/campaigns/{campaign_id}/audit", response_model=list[TimelineEntry])
async def campaign_timeline(campaign_id: str, ctx: AppContext = Depends(get_ctx)) -> list[TimelineEntry]:
    if await ctx.db.get_campaign(campaign_id) is None:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")
    events = await ctx.db.list_events(campaign_id)
    audit = await ctx.coordinator.audit.history(campaign_id)
    entries = [e for e in (_from_event(ev) for ev in events) if e is not None]
    entries += [_from_audit(a) for a in audit]
    return sorted(entries, key=lambda e: e.at)


def _from_event(ev: Event) -> TimelineEntry | None:
    m, d, t = ev.move, ev.data, ev.type
    n = m.move if m else d.get("move")
    if t is EventType.CAMPAIGN_STARTED:
        return TimelineEntry(at=ev.at, kind="campaign", summary=f"Partida iniciada contra {d.get('origin')}",
                             details={k: d.get(k) for k in ("planner", "unattended")})
    if t is EventType.MOVE_PLANNED and m:
        plan = m.plan.model_dump(mode="json") if m.plan else {}
        who = "IA" if m.plan and m.plan.source == "ai" else "regras"
        return TimelineEntry(at=ev.at, kind="decision", move=n,
                             summary=f"Lance {n}: {who} escolheu '{m.title}'. Hipotese: {m.plan.hypothesis if m.plan else '-'}",
                             details={"test_id": m.test_id, "plan": plan})
    if t is EventType.APPROVAL_REQUESTED:
        return TimelineEntry(at=ev.at, kind="approval_requested", move=n,
                             summary=f"Lance {n}: aguardando aprovacao humana")
    if t is EventType.APPROVAL_RESOLVED:
        approval = d.get("approval") or (m.approval.value if m else None)
        actor = d.get("actor") or "operator"
        return TimelineEntry(at=ev.at, kind="approval", move=n,
                             summary=f"Lance {n}: {'aprovado' if approval == 'approved' else 'negado'} por {actor}",
                             details={"approval": approval, "actor": actor, "reason": d.get("reason")})
    if t is EventType.FINDING_CREATED and m:
        return TimelineEntry(at=ev.at, kind="result", move=n,
                             summary=f"Lance {n}: {m.title} -> {m.status.value if m.status else '-'}"
                                     f" / {m.grade.value if m.grade else '-'}"
                                     + (f" ({m.verdict.value})" if m.verdict else ""),
                             details={"status": m.status, "grade": m.grade, "verdict": m.verdict,
                                      "evidence_ids": [e.id for e in m.evidence]})
    if t is EventType.SCOPE_BLOCKED:
        return TimelineEntry(at=ev.at, kind="blocked", summary=f"Bloqueado: {d.get('reason')}",
                             details={k: d.get(k) for k in ("url", "method", "reason")})
    if t is EventType.STOP_REQUESTED:
        return TimelineEntry(at=ev.at, kind="stop", summary=f"Parada de emergencia por {d.get('actor', 'operator')}")
    if t is EventType.CAMPAIGN_FINISHED:
        return TimelineEntry(at=ev.at, kind="campaign", summary=f"Partida encerrada: {d.get('state')}",
                             details={k: d.get(k) for k in ("state", "accuracy", "requests", "reason")})
    return None  # test_started / score_updated ficam so no ao vivo


def _from_audit(a: AuditEntry) -> TimelineEntry:
    if a.allowed:
        summary = f"{a.method} {a.url} -> {a.status_code if a.status_code is not None else a.reason or '-'}"
    else:
        summary = f"BLOQUEADO {a.method} {a.url}: {a.reason}"
    return TimelineEntry(at=a.at, kind="command" if a.allowed else "blocked", summary=summary,
                         details={"method": a.method, "url": a.url, "allowed": a.allowed,
                                  "status_code": a.status_code, "response_sha256": a.response_sha256,
                                  "reason": a.reason})

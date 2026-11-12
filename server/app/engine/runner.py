"""Orquestracao da campanha: planner -> (aprovacao) -> executor -> evaluator.

Assinatura exportada para a Plataforma (ver ``app.interfaces.CampaignRunner``):
    run_campaign(campaign_id, config, sink) -> Campaign
"""

from __future__ import annotations

from app.engine.checks.base import CheckContext, CheckOutcome, CheckSpec
from app.engine.evaluator import compute_score, grade_for
from app.engine.executor import Fetcher
from app.engine.planner import Planner
from app.engine.scope import ScopeGuard, utcnow
from app.interfaces import EventSink
from app.models import (
    Approval, Campaign, CampaignConfig, CampaignState, Confidence, Event, EventType,
    Grade, Move, Severity, Status,
)
from app.redact import sanitize_url


async def _emit(sink: EventSink, cid: str, type_: EventType, move: Move | None = None, **data) -> None:
    await sink.emit(Event(campaign_id=cid, type=type_, at=utcnow(),
                          move=move.model_copy(deep=True) if move else None, data=data))


async def run_campaign(campaign_id: str, config: CampaignConfig, sink: EventSink) -> Campaign:
    campaign = Campaign(id=campaign_id, config=config, state=CampaignState.RUNNING, created_at=utcnow())
    guard = ScopeGuard(config)

    window = guard.window_ok()
    if not window.allowed:  # campanha recusa rodar fora da janela
        await _emit(sink, campaign_id, EventType.SCOPE_BLOCKED, reason=window.reason)
        campaign.state, campaign.finished_at = CampaignState.FAILED, utcnow()
        await _emit(sink, campaign_id, EventType.CAMPAIGN_FINISHED, state=campaign.state.value, reason=window.reason)
        return campaign

    fetcher = Fetcher(campaign_id, config, sink, guard)
    ctx = CheckContext(config, fetcher, guard)
    planner = Planner(config)
    await _emit(sink, campaign_id, EventType.CAMPAIGN_STARTED, origin=sanitize_url(config.origin))

    try:
        for number, spec in enumerate(planner.plan(), start=1):
            if await sink.should_stop():
                campaign.state = CampaignState.STOPPED
                break
            move = _new_move(number, spec)
            campaign.moves.append(move)
            ctx.move_no = number
            await _emit(sink, campaign_id, EventType.MOVE_PLANNED, move)

            if spec.needs_approval and not await _approved(sink, campaign_id, move):
                if await sink.should_stop():
                    campaign.state = CampaignState.STOPPED
                    break
                continue  # negado: aparece no relatorio, fora do score

            reason = planner.skip_reason(spec, ctx)
            if reason:
                _finish(move, CheckOutcome(Status.INCONCLUSIVE, reason, confidence=Confidence.LOW), spec, grade=Grade.MISS)
            else:
                await _emit(sink, campaign_id, EventType.TEST_STARTED, move)
                move.started_at = utcnow()
                _finish(move, await _run_check(spec, ctx), spec)
            await _emit(sink, campaign_id, EventType.FINDING_CREATED, move)

            campaign.score = compute_score(campaign.moves)
            await _emit(sink, campaign_id, EventType.SCORE_UPDATED,
                        accuracy=campaign.score.accuracy, eval_bar=campaign.score.eval_bar)
        else:
            campaign.state = CampaignState.FINISHED
    finally:
        await fetcher.aclose()

    campaign.score = compute_score(campaign.moves)
    campaign.finished_at = utcnow()
    await _emit(sink, campaign_id, EventType.CAMPAIGN_FINISHED, state=campaign.state.value,
                accuracy=campaign.score.accuracy, requests=guard.requests_made)
    return campaign


def _new_move(number: int, spec: CheckSpec) -> Move:
    return Move(
        move=number, test_id=spec.test_id, title=spec.title, phase=spec.phase, profile=spec.profile,
        wstg=spec.wstg, owasp_top10=spec.owasp, severity=spec.severity,
        approval=Approval.PENDING if spec.needs_approval else Approval.NOT_REQUIRED,
    )


async def _approved(sink: EventSink, cid: str, move: Move) -> bool:
    await _emit(sink, cid, EventType.APPROVAL_REQUESTED, move)
    decision = await sink.wait_approval(cid, move.model_copy(deep=True))
    move.approval = Approval.APPROVED if decision is Approval.APPROVED else Approval.DENIED
    await _emit(sink, cid, EventType.APPROVAL_RESOLVED, move)
    return move.approval is Approval.APPROVED


async def _run_check(spec: CheckSpec, ctx: CheckContext) -> CheckOutcome:
    """Cada lance isolado: qualquer erro vira 'inconclusivo' (ASI08), sem vazar a excecao."""
    try:
        return await spec.fn(ctx)
    except Exception:  # noqa: BLE001
        return CheckOutcome(Status.INCONCLUSIVE, "Erro interno ao executar o teste.", confidence=Confidence.LOW)


def _finish(move: Move, out: CheckOutcome, spec: CheckSpec, grade: Grade | None = None) -> None:
    move.status = out.status
    move.severity = out.severity or spec.severity
    move.grade = grade or grade_for(out.status, move.severity, out.exemplary)
    move.confidence = out.confidence
    move.evidence = out.evidence
    move.explanation = out.explanation
    move.recommendation = out.recommendation
    move.finished_at = utcnow()
    move.started_at = move.started_at or move.finished_at

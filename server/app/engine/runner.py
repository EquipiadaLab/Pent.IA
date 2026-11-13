"""Orquestracao da campanha (agente autonomo dentro de limites).

Ciclo por lance:
  observar -> PLANEJAR (IA, plano gravado antes) -> aprovar (humano ou
  pre-aprovacao do servidor) -> EXECUTAR (arbitro em cada requisicao) ->
  CONFIRMAR (segunda observacao independente) -> registrar.

Assinatura exportada para a Plataforma (ver ``app.interfaces.CampaignRunner``):
    run_campaign(campaign_id, config, sink, *, llm=None) -> Campaign
``llm`` e opcional: sem ele, o planejamento usa as regras do catalogo.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from app.agents.pent import Pent
from app.authorization import explain_refusal, is_authorized
from app.engine.checks.base import CheckContext, CheckOutcome, CheckSpec
from app.engine.evaluator import compute_score, grade_for
from app.engine.executor import Fetcher
from app.engine.planner import Planner, rules_plan
from app.engine.reproduce import reproduce_steps
from app.engine.scope import ScopeGuard, utcnow
from app.interfaces import EventSink, LLMClient
from app.models import (
    Approval, AuditEntry, Campaign, CampaignConfig, CampaignState, Confidence, Event, EventType,
    Grade, Move, MovePlan, Status, Verdict,
)
from app.schemas.agents_contract import TacticDecisionContext, TechniqueRecommendation
from app.redact import sanitize_url


async def _emit(sink: EventSink, cid: str, type_: EventType, mv: Move | None = None, /, **data) -> None:
    await sink.emit(Event(campaign_id=cid, type=type_, at=utcnow(),
                          move=mv.model_copy(deep=True) if mv else None, data=data))


async def run_campaign(campaign_id: str, config: CampaignConfig, sink: EventSink,
                       *, llm: LLMClient | None = None) -> Campaign:
    campaign = Campaign(id=campaign_id, config=config, state=CampaignState.RUNNING, created_at=utcnow())
    guard = ScopeGuard(config)

    refusal = _refusal(config, guard)
    if refusal:  # alvo nao autorizado ou fora da janela: nenhuma requisicao sai
        await sink.audit(AuditEntry(campaign_id=campaign_id, at=utcnow(), method="-",
                                    url=sanitize_url(config.origin), allowed=False, reason=refusal))
        await _emit(sink, campaign_id, EventType.SCOPE_BLOCKED, url=sanitize_url(config.origin), reason=refusal)
        campaign.state, campaign.finished_at = CampaignState.FAILED, utcnow()
        await _emit(sink, campaign_id, EventType.CAMPAIGN_FINISHED, state=campaign.state.value, reason=refusal)
        return campaign

    fetcher = Fetcher(campaign_id, config, sink, guard)
    ctx = CheckContext(config, fetcher, guard)
    planner = Planner(config, llm)
    pent = Pent()
    await _emit(sink, campaign_id, EventType.CAMPAIGN_STARTED, origin=sanitize_url(config.origin),
                planner="ai" if planner.ai_active else "rules", unattended=False)

    try:
        # Nenhuma requisicao de abertura e feita aqui. A primeira observacao
        # HTTP deve pertencer a um lance que o responsavel acabou de aprovar.
        number = 0
        while True:
            if await sink.should_stop():
                campaign.state = CampaignState.STOPPED
                break

            # Limite de lances escolhido na criacao: encerra ao atingi-lo, antes
            # de planejar o proximo lance (garante no maximo ``max_moves`` lances).
            if config.max_moves is not None and len(campaign.moves) >= config.max_moves:
                campaign.state = CampaignState.FINISHED
                break

            pent_choice = _pent_choice(campaign_id, config, campaign.moves, guard, planner, pent)
            if pent_choice is not None:
                spec, plan, recommendation = pent_choice
            else:
                # Fallback temporario para checks que ainda nao possuem um
                # agente especialista. Continua sendo catalogo fechado e,
                # abaixo, tambem exige aprovacao humana.
                choice = await planner.next_move(ctx, campaign.moves)
                if choice is None:
                    campaign.state = CampaignState.FINISHED
                    break
                spec, plan = choice
                recommendation = None

            number += 1
            move = _new_move(number, spec, plan, recommendation)
            campaign.moves.append(move)
            ctx.move_no = number

            # Regra da arquitetura multiagente: TODO lance, inclusive
            # passivo, aguarda uma decisao humana antes de executar.
            approved = await _approval(sink, campaign_id, move)
            if not approved:
                if await sink.should_stop():
                    campaign.state = CampaignState.STOPPED
                    break
                continue  # negado: aparece no relatorio, fora do score

            reason = planner.skip_reason(spec, ctx)
            if reason:
                _finish(move, CheckOutcome(Status.INCONCLUSIVE, reason, confidence=Confidence.LOW), spec,
                        grade=Grade.MISS)
            else:
                await _emit(sink, campaign_id, EventType.TEST_STARTED, move)
                move.started_at = utcnow()
                _finish(move, await _run_check(spec, ctx), spec)
                if move.status in (Status.FAIL, Status.WARNING) and not await sink.should_stop():
                    await _confirm(move, spec, config, fetcher, guard)
            move.reproduce = reproduce_steps(config.origin, move)
            await _emit(sink, campaign_id, EventType.FINDING_CREATED, move)

            campaign.score = compute_score(campaign.moves)
            await _emit(sink, campaign_id, EventType.SCORE_UPDATED, accuracy=campaign.score.accuracy,
                        eval_bar=campaign.score.eval_bar, score=campaign.score.model_dump(mode="json"))
    finally:
        await fetcher.aclose()

    campaign.score = compute_score(campaign.moves)
    campaign.finished_at = utcnow()
    await _emit(sink, campaign_id, EventType.SCORE_UPDATED, accuracy=campaign.score.accuracy,
                eval_bar=campaign.score.eval_bar, score=campaign.score.model_dump(mode="json"))
    await _emit(sink, campaign_id, EventType.CAMPAIGN_FINISHED, state=campaign.state.value,
                accuracy=campaign.score.accuracy, requests=guard.requests_made)
    return campaign


def _refusal(config: CampaignConfig, guard: ScopeGuard) -> str | None:
    for url in [config.origin, *config.extra_origins]:
        if not is_authorized(url):
            return explain_refusal(sanitize_url(url))
    window = guard.window_ok()
    return None if window.allowed else window.reason


def _pent_choice(
    campaign_id: str,
    config: CampaignConfig,
    played: list[Move],
    guard: ScopeGuard,
    planner: Planner,
    pent: Pent,
) -> tuple[CheckSpec, MovePlan, TechniqueRecommendation] | None:
    """Pede sugestoes ao Pent antes do fallback do planner existente.

    Pent e Recon so recebem ids que ja pertencem ao catalogo fechado e que o
    runner considera elegiveis. Mesmo assim, Pent valida o id novamente. Esta
    funcao NAO faz rede e NAO cria permissao de execucao.
    """
    finished = {move.test_id for move in played}
    denied = {move.test_id for move in played if move.approval is Approval.DENIED}
    available = [
        spec.test_id
        for spec in planner.plan()
        if spec.test_id not in finished and spec.profile in config.allowed_profiles
    ]
    context = TacticDecisionContext(
        campaign_id=campaign_id,
        available_test_ids=available,
        executed_test_ids=[move.test_id for move in played if move.status is not None],
        denied_test_ids=sorted(denied),
        remaining_requests=max(0, config.max_total_requests - guard.requests_made),
        observed_facts={"origin_scheme": urlsplit(config.origin).scheme.lower()},
    )
    decision = pent.choose_next(context)
    recommendation = decision.selected
    if recommendation is None:
        return None

    # Pent ja valida, mas o runner segue sendo o arbitro final.
    spec = planner.suggest(recommendation.test_id)
    if spec is None or spec.test_id not in available:
        return None

    plan = rules_plan(spec).model_copy(
        update={
            "rationale": (
                f"Pent selecionou a recomendacao do agente {recommendation.agent}: "
                f"{recommendation.rationale}"
            )
        }
    )
    return spec, plan, recommendation


def _new_move(
    number: int,
    spec: CheckSpec,
    plan: MovePlan,
    recommendation: TechniqueRecommendation | None = None,
) -> Move:
    provenance = {}
    if recommendation is not None:
        attack = recommendation.attack
        provenance = {
            "recommended_by": recommendation.agent,
            "attack_tactic_id": attack.tactic_id,
            "attack_tactic_name": attack.tactic_name,
            "attack_technique_id": attack.technique_id,
            "attack_technique_name": attack.technique_name,
            "attack_url": attack.url,
        }
    return Move(
        move=number, test_id=spec.test_id, title=spec.title, phase=spec.phase, profile=spec.profile,
        wstg=spec.wstg, owasp_top10=spec.owasp, severity=spec.severity, impact=spec.impact,
        exploitation_scenario=spec.exploitation_scenario or spec.impact, plan=plan,
        # Todo teste da nova arquitetura comeca pendente de decisao humana.
        approval=Approval.PENDING,
        **provenance,
    )


async def _approval(sink: EventSink, cid: str, move: Move) -> bool:
    """Aprovacao humana obrigatoria para TODO lance.

    Mesmo que a campanha tenha sido marcada como ``unattended``, este fluxo
    nao usa pre-aprovacao automatica: sem clique de aprovar, nao ha execucao.
    A parada de emergencia vence qualquer aprovacao pendente.
    """
    await _emit(sink, cid, EventType.MOVE_PLANNED, move)
    await _emit(sink, cid, EventType.APPROVAL_REQUESTED, move, move=move.move)
    decision = await sink.wait_approval(cid, move.model_copy(deep=True))
    move.approval = Approval.APPROVED if decision is Approval.APPROVED else Approval.DENIED
    await _emit(sink, cid, EventType.APPROVAL_RESOLVED, move, move=move.move, approval=move.approval.value)
    return move.approval is Approval.APPROVED


async def _run_check(spec: CheckSpec, ctx: CheckContext) -> CheckOutcome:
    """Cada lance isolado: qualquer erro vira 'inconclusivo' (ASI08), sem vazar a excecao."""
    try:
        return await spec.fn(ctx)
    except Exception:  # noqa: BLE001
        return CheckOutcome(Status.INCONCLUSIVE, "Erro interno ao executar o teste.", confidence=Confidence.LOW)


async def _confirm(move: Move, spec: CheckSpec, config: CampaignConfig, fetcher: Fetcher,
                   guard: ScopeGuard) -> None:
    """Item 5: repete o MESMO teste (mesmas requisicoes seguras, novas respostas).

    - mesmo resultado      -> confirmed (confianca alta)
    - nao se reproduziu    -> discarded (sai do score; nota vira inconclusiva)
    - sem resposta/limite  -> inconclusive
    """
    replay = CheckContext(config, fetcher, guard, replay=True)
    replay.move_no = move.move
    second = await _run_check(spec, replay)
    move.evidence = [*move.evidence, *second.evidence]
    if second.status is Status.INCONCLUSIVE:
        move.verdict = Verdict.INCONCLUSIVE
        move.confidence = Confidence.MEDIUM
    elif second.status is move.status:
        move.verdict = Verdict.CONFIRMED
        move.confidence = Confidence.HIGH
    else:
        move.verdict = Verdict.DISCARDED
        move.confidence = Confidence.LOW
        move.grade = Grade.INCONCLUSIVE
        move.explanation = (f"{move.explanation} Descartado: na segunda observacao o resultado foi "
                            f"'{second.status.value}' (nao se reproduziu).")


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

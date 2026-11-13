"""Endpoints de status e informacao (caminhos NOVOS, aditivos).

- GET /status ...................... saude detalhada (API, banco, motor, IA)
- GET /catalog ..................... testes que o agente pode jogar (o "tabuleiro")
- GET /scope ....................... regras de engajamento impostas pelo servidor
- GET /campaigns/{id}/status ....... progresso resumido de uma partida

Nada aqui expoe segredo: sem credenciais, sem conta AWS, sem mensagens de erro internas.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.context import AppContext, get_ctx
from app.api.routes import _MAX_RPS, _MAX_TIMEOUT_S, _MAX_TOTAL, _SAFE_METHODS, _SAFE_PROFILES
from app.authorization import _block_private, accepts_any_target, authorized_origins, default_target
from app.cve.correlation import correlate_campaign
from app.cve.models import CveMatch
from app.authorization import (
    _block_private,
    accepts_any_target,
    authorized_origins,
    default_target,
    locked_target,
)
from app.engine.scope import normalize_origin
from app.engine.checks import CATALOG
from app.models import Approval, CampaignState, Phase, Profile, Score, Severity, Status
from app.policy import preapproval

router = APIRouter()

VERSION = "0.2.0"
_STARTED = time.monotonic()
_LLM_CACHE_S = 60.0
_llm_check: dict = {"at": 0.0, "result": None}


# ------------------------------------------------------------------ modelos
class ComponentStatus(BaseModel):
    status: Literal["ok", "degraded", "error", "disabled", "unchecked"]
    detail: str | None = None
    latency_ms: int | None = None


class StatusResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    time: datetime
    uptime_s: int
    engine_mode: Literal["real", "sample"]
    planner: Literal["ai", "rules"]
    models: dict[str, str | None]
    components: dict[str, ComponentStatus]
    campaigns: dict[str, int]


class CatalogTest(BaseModel):
    test_id: str
    title: str
    phase: Phase
    profile: Profile
    severity: Severity
    wstg: str
    owasp_top10: str
    needs_approval: bool
    hypothesis: str
    expected: str
    impact: str


class PreapprovalInfo(BaseModel):
    tests: list[str]
    approved_by: str | None
    valid_until: str | None
    active: list[str] = Field(description="Testes com pre-aprovacao VALIDA agora")


class ScopeResponse(BaseModel):
    locked_target: str | None = Field(description="Se preenchido, o sistema SO testa este alvo (trava forte)")
    authorized_targets: list[str]
    accepts_any_target: bool = Field(description="True = modo aberto (qualquer URL publica); False = travado/lista")
    default_target: str | None = Field(description="Alvo usado quando o front nao envia origin (modo aberto)")
    blocks_private_targets: bool = Field(description="Rede interna/privada sempre bloqueada (anti-SSRF)")
    allowed_methods: list[str]
    allowed_profiles: list[Profile]
    blocked_profiles: list[Profile]
    limits: dict[str, float]
    preapproval: PreapprovalInfo


class PendingApproval(BaseModel):
    move: int
    test_id: str
    title: str
    hypothesis: str | None = None


class CurrentMove(BaseModel):
    move: int
    test_id: str
    title: str
    stage: Literal["awaiting_approval", "running"]


class CampaignStatusResponse(BaseModel):
    id: str
    state: CampaignState
    origin: str
    unattended: bool
    progress: dict[str, int]
    current_move: CurrentMove | None
    pending_approvals: list[PendingApproval]
    score: Score | None
    last_seq: int = Field(description="Use como 'since' no WebSocket/polling")
    created_at: datetime
    finished_at: datetime | None
    elapsed_s: int


class AgentParticipation(BaseModel):
    """Participacao de UM agente especialista (Recon, Discovery, etc.) na campanha."""

    agent: str = Field(description="Nome do agente, ex.: 'Recon', 'Collection'. '-' = lance sem agente (fallback do catalogo).")
    tactic_id: str | None = Field(description="Tatica MITRE ATT&CK, ex.: 'TA0043'.")
    tactic_name: str | None = None
    moves_recommended: int = Field(description="Quantos lances este agente recomendou e foram jogados.")
    moves_approved: int
    moves_denied: int
    findings: int = Field(description="Lances com status fail/warning confirmados (contam no placar).")
    techniques_used: list[str] = Field(default_factory=list, description="IDs de tecnica MITRE observados, ex.: ['T1595', 'T1213'].")


class AgentsParticipationResponse(BaseModel):
    campaign_id: str
    agents: list[AgentParticipation]


class CvesResponse(BaseModel):
    campaign_id: str
    matches: list[CveMatch]


# ------------------------------------------------------------------ /status
@router.get("/status", response_model=StatusResponse)
async def status(
    check_llm: bool = Query(False, description="Faz uma chamada curta ao Bedrock (cache de 60 s)"),
    ctx: AppContext = Depends(get_ctx),
) -> StatusResponse:
    components: dict[str, ComponentStatus] = {"api": ComponentStatus(status="ok")}

    counts: dict[str, int] = {}
    t0 = time.monotonic()
    try:
        counts = await ctx.db.ping()
        components["database"] = ComponentStatus(status="ok", latency_ms=_ms(t0))
    except Exception:  # noqa: BLE001
        components["database"] = ComponentStatus(status="error", detail="banco indisponivel")

    components["engine"] = ComponentStatus(
        status="ok" if ctx.using_real_engine else "degraded",
        detail=f"{len(CATALOG)} testes no catalogo" if ctx.using_real_engine else "motor de exemplo (sample)",
    )
    components["llm"] = await _llm_status(ctx, check_llm)

    degraded = any(c.status in ("error", "degraded") for c in components.values())
    s = ctx.settings
    return StatusResponse(
        status="degraded" if degraded else "ok",
        version=VERSION,
        time=datetime.now(UTC),
        uptime_s=int(time.monotonic() - _STARTED),
        engine_mode="real" if ctx.using_real_engine else "sample",
        planner="ai" if ctx.using_real_engine and s.planner_model_id else "rules",
        models={"coach_judge_summary": s.bedrock_model_id, "planner": s.planner_model_id},
        components=components,
        campaigns={"total": sum(counts.values()), **{st.value: counts.get(st.value, 0) for st in CampaignState}},
    )


async def _llm_status(ctx: AppContext, check: bool) -> ComponentStatus:
    if not ctx.settings.llm_enabled:
        return ComponentStatus(status="disabled", detail="sem credenciais da AWS ou LLM_ENABLED=false")
    if not check:
        cached = _llm_check["result"]
        return cached or ComponentStatus(status="unchecked", detail="use ?check_llm=true para testar o Bedrock")
    if _llm_check["result"] and time.monotonic() - _llm_check["at"] < _LLM_CACHE_S:
        return _llm_check["result"]
    t0 = time.monotonic()
    try:
        llm = ctx.report_builder._llm  # mesmo cliente do relatorio
        reply = await asyncio.wait_for(llm.complete("Responda apenas: ok", "ping", max_tokens=10), 20)
        result = ComponentStatus(status="ok" if reply else "degraded", latency_ms=_ms(t0),
                                 detail="Bedrock respondeu")
    except Exception as exc:  # noqa: BLE001 - so o tipo do erro, nunca a mensagem
        hint = "credenciais expiradas?" if "Credential" in type(exc).__name__ or "LLMError" in type(exc).__name__ else ""
        result = ComponentStatus(status="error", latency_ms=_ms(t0),
                                 detail=f"Bedrock nao respondeu ({type(exc).__name__}) {hint}".strip())
    _llm_check.update(at=time.monotonic(), result=result)
    return result


def _ms(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)


# ------------------------------------------------------------------ /catalog
@router.get("/catalog", response_model=list[CatalogTest])
async def catalog() -> list[CatalogTest]:
    return [
        CatalogTest(test_id=c.test_id, title=c.title, phase=c.phase, profile=c.profile, severity=c.severity,
                    wstg=c.wstg, owasp_top10=c.owasp, needs_approval=c.needs_approval,
                    hypothesis=c.hypothesis, expected=c.expected, impact=c.impact)
        for c in CATALOG
    ]


# ------------------------------------------------------------------ /scope
@router.get("/scope", response_model=ScopeResponse)
async def scope() -> ScopeResponse:
    import os

    open_mode = accepts_any_target()
    locked = locked_target()
    targets = [normalize_origin(locked) or locked] if locked else sorted(authorized_origins())
    tests = [t.strip() for t in os.getenv("PREAPPROVED_TESTS", "").split(",") if t.strip()]
    return ScopeResponse(
        locked_target=locked,
        authorized_targets=targets,
        accepts_any_target=open_mode,
        default_target=default_target() if open_mode else None,
        blocks_private_targets=_block_private(),
        allowed_methods=list(_SAFE_METHODS),
        allowed_profiles=sorted(_SAFE_PROFILES, key=lambda p: p.value),
        blocked_profiles=[Profile.INTRUSIVE],
        limits={"max_requests_per_second": _MAX_RPS, "max_total_requests": _MAX_TOTAL,
                "request_timeout_s": _MAX_TIMEOUT_S},
        preapproval=PreapprovalInfo(
            tests=tests,
            approved_by=os.getenv("PREAPPROVED_BY") or None,
            valid_until=os.getenv("PREAPPROVED_UNTIL") or None,
            active=[t for t in tests if preapproval(t).approved],
        ),
    )


# ------------------------------------------------------------------ /campaigns/{id}/status
@router.get("/campaigns/{campaign_id}/status", response_model=CampaignStatusResponse)
async def campaign_status(campaign_id: str, ctx: AppContext = Depends(get_ctx)) -> CampaignStatusResponse:
    c = await ctx.db.get_campaign(campaign_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")
    total = len(c.config.only_tests) if c.config.only_tests is not None else len(CATALOG)
    played = sum(1 for m in c.moves if m.status is not None or m.approval is Approval.DENIED)
    pending = [m for m in c.moves if m.approval is Approval.PENDING]
    open_moves = [m for m in c.moves if m.status is None and m.approval is not Approval.DENIED]
    current = None
    final = c.state in (CampaignState.FINISHED, CampaignState.STOPPED, CampaignState.FAILED)
    if open_moves and not final:
        m = open_moves[-1]
        current = CurrentMove(move=m.move, test_id=m.test_id, title=m.title,
                              stage="awaiting_approval" if m.approval is Approval.PENDING else "running")
    end = c.finished_at or datetime.now(UTC)
    return CampaignStatusResponse(
        id=c.id, state=c.state, origin=c.config.origin, unattended=c.config.unattended,
        progress={"played": played, "total": total, "percent": round(100 * played / total) if total else 100},
        current_move=current,
        pending_approvals=[PendingApproval(move=m.move, test_id=m.test_id, title=m.title,
                                           hypothesis=m.plan.hypothesis if m.plan else None) for m in pending],
        score=c.score,
        last_seq=await ctx.db.last_seq(campaign_id),
        created_at=c.created_at,
        finished_at=c.finished_at,
        elapsed_s=max(0, int((end - c.created_at).total_seconds())),
    )


# ------------------------------------------------------------------ /campaigns/{id}/agents
@router.get("/campaigns/{campaign_id}/agents", response_model=AgentsParticipationResponse)
async def campaign_agents(campaign_id: str, ctx: AppContext = Depends(get_ctx)) -> AgentsParticipationResponse:
    """Participacao de cada agente que o Pent convocou nesta campanha.

    Agregado a partir de ``Move.recommended_by``/``attack_tactic_id``/``attack_technique_id``,
    ja preenchidos pelo runner quando Pent escolhe a recomendacao de um agente (ver
    ``app/engine/runner.py:_new_move``). Lances tocados pelo fallback do catalogo (ainda sem
    agente especialista) aparecem agrupados como agente ``"-"``.
    """
    c = await ctx.db.get_campaign(campaign_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")

    buckets: dict[str, dict] = {}
    order: list[str] = []
    for mv in c.moves:
        agent = mv.recommended_by or "-"
        if agent not in buckets:
            buckets[agent] = {
                "tactic_id": mv.attack_tactic_id,
                "tactic_name": mv.attack_tactic_name,
                "moves_recommended": 0,
                "moves_approved": 0,
                "moves_denied": 0,
                "findings": 0,
                "techniques_used": set(),
            }
            order.append(agent)
        bucket = buckets[agent]
        bucket["moves_recommended"] += 1
        if mv.approval is Approval.APPROVED:
            bucket["moves_approved"] += 1
        elif mv.approval is Approval.DENIED:
            bucket["moves_denied"] += 1
        if mv.status in (Status.FAIL, Status.WARNING) and mv.verdict != "discarded":
            bucket["findings"] += 1
        if mv.attack_technique_id:
            bucket["techniques_used"].add(mv.attack_technique_id)

    agents = [
        AgentParticipation(
            agent=name,
            tactic_id=buckets[name]["tactic_id"],
            tactic_name=buckets[name]["tactic_name"],
            moves_recommended=buckets[name]["moves_recommended"],
            moves_approved=buckets[name]["moves_approved"],
            moves_denied=buckets[name]["moves_denied"],
            findings=buckets[name]["findings"],
            techniques_used=sorted(buckets[name]["techniques_used"]),
        )
        for name in order
    ]
    return AgentsParticipationResponse(campaign_id=campaign_id, agents=agents)


# ------------------------------------------------------------------ /campaigns/{id}/cves
@router.get("/campaigns/{campaign_id}/cves", response_model=CvesResponse)
async def campaign_cves(campaign_id: str, ctx: AppContext = Depends(get_ctx)) -> CvesResponse:
    """CVEs publicos (NVD) correlacionados as tecnologias REALMENTE observadas na campanha.

    So correlaciona o que um check ja capturou como evidencia (headers Server/
    X-Powered-By, mascarados pela allowlist). Sem evidencia de tecnologia, a
    lista de ``matches`` vem vazia -- nunca ha CVE "generico" por categoria de
    achado. Pode ser lento na primeira chamada (consulta externa a NVD); o
    resultado por termo fica em cache por 1h.
    """
    c = await ctx.db.get_campaign(campaign_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")
    if ctx.nvd_client is None:
        return CvesResponse(campaign_id=campaign_id, matches=[])
    matches = await correlate_campaign(c, ctx.nvd_client)
    return CvesResponse(campaign_id=campaign_id, matches=matches)

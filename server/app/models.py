"""Contrato compartilhado do Pentest Chess.

ATENCAO: este arquivo e o ponto de encontro entre o Motor (engine) e a
Plataforma (api/db/reporter) e o frontend. Mudancas so por PR avisado ao
outro trilho, mantendo compatibilidade (campos novos sempre opcionais).

Vocabulario:
- ``status``   = RESULTADO do teste (so existe depois de executado).
- ``approval`` = ESTADO DE APROVACAO humana (fluxo, independente do resultado).
- ``grade``    = nota estilo Chess.com derivada de status x severity.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------
class Status(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Confidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Grade(StrEnum):
    """Notas estilo Chess.com. ``inconclusive`` fica fora do score."""

    BRILLIANT = "brilliant"
    GREAT = "great"
    BEST = "best"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    MISS = "miss"
    BLUNDER = "blunder"
    INCONCLUSIVE = "inconclusive"


class Approval(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class Profile(StrEnum):
    """Perfil de intrusividade do teste. ``intrusive`` e bloqueado por padrao."""

    PASSIVE = "passive"
    ACTIVE_LIGHT = "active_light"
    INTRUSIVE = "intrusive"


class Phase(StrEnum):
    OPENING = "opening"  # recon: TLS, redirect, robots, fingerprint
    MIDDLEGAME = "middlegame"  # configuracao: headers, cookies, CORS
    ENDGAME = "endgame"  # ativo leve, com aprovacao humana


class CampaignState(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    STOPPED = "stopped"  # parada de emergencia (resultados parciais preservados)
    FINISHED = "finished"
    FAILED = "failed"


class Verdict(StrEnum):
    """Item 5 do desafio: o achado foi reconfirmado na evidencia real?"""

    CONFIRMED = "confirmed"  # reproduziu na segunda observacao
    DISCARDED = "discarded"  # nao se reproduziu (falso positivo/instabilidade)
    INCONCLUSIVE = "inconclusive"  # nao foi possivel reconfirmar


class EventType(StrEnum):
    CAMPAIGN_STARTED = "campaign_started"
    MOVE_PLANNED = "move_planned"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    TEST_STARTED = "test_started"
    FINDING_CREATED = "finding_created"
    SCOPE_BLOCKED = "scope_blocked"
    SCORE_UPDATED = "score_updated"
    STOP_REQUESTED = "stop_requested"
    CAMPAIGN_FINISHED = "campaign_finished"


# --------------------------------------------------------------------------
# Escopo / regras de engajamento (configuracao da campanha, nunca constante)
# --------------------------------------------------------------------------
class CampaignConfig(BaseModel):
    origin: str = Field(default="", description="Origem exata: esquema + host + porta. Ex.: https://alvo.com. Vazio = usa DEFAULT_TARGET do servidor.")
    extra_origins: list[str] = Field(
        default_factory=list,
        description="Origens adicionais em escopo (ex.: versao http:// para o lance de redirect).",
    )
    included_paths: list[str] = Field(default_factory=lambda: ["/"])
    excluded_paths: list[str] = Field(default_factory=list)
    allowed_profiles: list[Profile] = Field(
        default_factory=lambda: [Profile.PASSIVE, Profile.ACTIVE_LIGHT]
    )
    allowed_methods: list[str] = Field(default_factory=lambda: ["GET", "OPTIONS"])
    max_requests_per_second: float = 2.0
    max_total_requests: int = 200
    request_timeout_s: float = 10.0
    window_start: datetime | None = None
    window_end: datetime | None = None
    authorized_by: str = Field(description="Quem autorizou o teste")
    authorized_at: datetime = Field(description="Quando foi autorizado")
    unattended: bool = Field(
        default=False,
        description="Execucao automatica (ex.: diaria): testes sensiveis so rodam se houver "
        "pre-aprovacao no SERVIDOR; sem ela, sao negados sem esperar humano.",
    )
    only_tests: list[str] | None = Field(
        default=None, description="Revalidacao: joga so estes test_ids (definido pelo servidor)."
    )


# --------------------------------------------------------------------------
# Lance
# --------------------------------------------------------------------------
class Evidence(BaseModel):
    """Evidencia bruta. Segredos/cookies DEVEM chegar aqui ja mascarados."""

    id: str
    request: str = Field(description='Ex.: "GET / HTTP/1.1"')
    response_status: int | None = None
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_sha256: str | None = None
    note: str | None = None


class MovePlan(BaseModel):
    """Item 3 do desafio: registrado ANTES de executar o lance."""

    hypothesis: str
    action: str
    expected_result: str
    stop_condition: str
    rationale: str | None = None  # por que este lance agora
    source: Literal["ai", "rules"] = "rules"  # quem planejou: IA ou regras (fallback)
    planned_at: datetime | None = None


class AIReview(BaseModel):
    """Parecer do 'juiz' (IA revisora) sobre o comentario da IA."""

    verdict: Literal["approved", "rejected"]
    issues: list[str] = Field(default_factory=list)


class Move(BaseModel):
    move: int = Field(description="Numero do lance (1-based)")
    test_id: str
    title: str
    phase: Phase
    profile: Profile
    wstg: str | None = Field(default=None, examples=["WSTG-SESS-02"])
    owasp_top10: str | None = Field(default=None, examples=["A07:2025"])

    approval: Approval = Approval.NOT_REQUIRED
    # Resultado: so preenchido depois de executado (None enquanto pendente/negado).
    status: Status | None = None
    severity: Severity = Severity.LOW
    grade: Grade | None = None
    confidence: Confidence | None = None

    evidence: list[Evidence] = Field(default_factory=list)
    explanation: str | None = None  # fato deterministico do teste (sempre presente apos executar)
    ai_explanation: str | None = None  # comentario da IA (Game Review), cita evidence ids; pode faltar
    recommendation: str | None = None  # "melhor lance": a correcao

    plan: MovePlan | None = None  # hipotese/acao/resultado esperado/parada (antes de executar)
    # Proveniencia da recomendacao multiagente. O executor ainda usa somente
    # ``test_id`` do catalogo fechado; estes campos existem para auditoria,
    # tela e relatorio e sao opcionais para manter os lances antigos compativeis.
    recommended_by: str | None = None
    attack_tactic_id: str | None = None
    attack_tactic_name: str | None = None
    attack_technique_id: str | None = None
    attack_technique_name: str | None = None
    attack_url: str | None = None
    verdict: Verdict | None = None  # so para achados (warning/fail): confirmado/descartado/inconclusivo
    impact: str | None = None  # impacto se o problema for explorado
    reproduce: list[str] = Field(default_factory=list)  # passos de reproducao (comandos curl)
    ai_review: AIReview | None = None  # juiz aprovou/rejeitou o ai_explanation

    started_at: datetime | None = None
    finished_at: datetime | None = None


# --------------------------------------------------------------------------
# Eventos, auditoria, campanha, relatorio
# --------------------------------------------------------------------------
class Event(BaseModel):
    seq: int = 0  # atribuido pela Plataforma (monotonico por campanha)
    campaign_id: str
    type: EventType
    at: datetime
    move: Move | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class AuditEntry(BaseModel):
    """Trilha append-only: toda requisicao (inclusive as bloqueadas)."""

    campaign_id: str
    at: datetime
    method: str
    url: str
    allowed: bool
    reason: str | None = None  # motivo do bloqueio
    status_code: int | None = None
    response_sha256: str | None = None
    actor: str = "agent"  # "agent" | nome de quem aprovou/parou


class Score(BaseModel):
    accuracy: float = Field(ge=0, le=100, description="Score ponderado; ignora inconclusivos")
    eval_bar: float = Field(ge=-100, le=100, description="Barra de avaliacao parcial")
    counts: dict[Grade, int] = Field(default_factory=dict)


class Campaign(BaseModel):
    id: str
    config: CampaignConfig
    state: CampaignState = CampaignState.CREATED
    created_at: datetime
    finished_at: datetime | None = None
    score: Score | None = None
    moves: list[Move] = Field(default_factory=list)


class KeyMoment(BaseModel):
    move: int
    summary: str


class TopRisk(BaseModel):
    move: int
    title: str
    why: str


class ExecutiveSummary(BaseModel):
    """Resumo executivo estruturado (JSON) para a tela."""

    headline: str
    risk_level: Literal["critico", "alto", "medio", "baixo"]
    plain_language: str
    top_risks: list[TopRisk] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    source: Literal["ai", "rules"] = "rules"


class Comparison(BaseModel):
    """Comparacao com a partida anterior do mesmo alvo (validacao continua)."""

    previous_campaign_id: str
    previous_accuracy: float | None = None
    accuracy_delta: float | None = None
    fixed: list[str] = Field(default_factory=list)  # test_ids que falhavam e agora passam
    new: list[str] = Field(default_factory=list)  # falhas que nao existiam antes
    still_failing: list[str] = Field(default_factory=list)


class TimelineEntry(BaseModel):
    """Item 8: registro cronologico unico de hipoteses, decisoes, aprovacoes, comandos e resultados."""

    at: datetime
    kind: Literal["campaign", "decision", "approval_requested", "approval", "command",
                  "blocked", "result", "score", "stop"]
    move: int | None = None
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class GameReview(BaseModel):
    """Relatorio estilo Game Review do Chess.com."""

    campaign: Campaign
    executive_summary: str | None = None
    key_moments: list[KeyMoment] = Field(default_factory=list)
    audit: list[AuditEntry] = Field(default_factory=list)
    summary: ExecutiveSummary | None = None  # versao estruturada do resumo
    comparison: Comparison | None = None  # vs. partida anterior do mesmo alvo

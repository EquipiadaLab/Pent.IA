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
from typing import Any

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
    origin: str = Field(description="Origem exata: esquema + host + porta. Ex.: https://alvo.com")
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


class GameReview(BaseModel):
    """Relatorio estilo Game Review do Chess.com."""

    campaign: Campaign
    executive_summary: str | None = None
    key_moments: list[KeyMoment] = Field(default_factory=list)
    audit: list[AuditEntry] = Field(default_factory=list)

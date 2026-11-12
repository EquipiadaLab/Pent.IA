"""Schemas PUBLICOS: unico formato que o frontend recebe.

Principios de seguranca:
- ``extra="forbid"`` + ``frozen``: campo novo precisa ser declarado aqui de
  proposito; nada vaza por acidente.
- Construcao SEMPRE por mapeamento explicito (``from_internal``), nunca por
  ``model_dump()`` do modelo interno.
- Texto vindo do alvo ou do LLM e DADO NAO CONFIAVEL: sai como texto puro ja
  saneado; o front deve renderizar como texto (sem innerHTML).
- Nunca saem: corpo bruto de respostas, valores de cookie/token, headers fora
  da allowlist, querystring de URL, mensagens/stack de excecao, prompts do LLM,
  credenciais, caminhos de arquivo do servidor, IDs internos de banco.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app import models as m
from app.redact import sanitize_headers, sanitize_url, scrub_text


class _Public(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ------------------------------ saida ------------------------------------
class PublicEvidence(_Public):
    id: str
    request: str
    response_status: int | None = None
    response_headers: dict[str, str] = Field(default_factory=dict)
    response_sha256: str | None = None
    note: str | None = None

    @classmethod
    def from_internal(cls, e: m.Evidence) -> PublicEvidence:
        return cls(
            id=e.id,
            request=scrub_text(e.request) or "",
            response_status=e.response_status,
            response_headers=sanitize_headers(e.response_headers),
            response_sha256=e.response_sha256,
            note=scrub_text(e.note),
        )


class PublicMove(_Public):
    move: int
    test_id: str
    title: str
    phase: m.Phase
    profile: m.Profile
    wstg: str | None = None
    owasp_top10: str | None = None
    approval: m.Approval
    status: m.Status | None = None
    severity: m.Severity
    grade: m.Grade | None = None
    confidence: m.Confidence | None = None
    evidence: list[PublicEvidence] = Field(default_factory=list)
    explanation: str | None = None  # texto puro, nao HTML
    ai_explanation: str | None = None  # texto puro, nao HTML
    recommendation: str | None = None  # texto puro, nao HTML
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def from_internal(cls, mv: m.Move) -> PublicMove:
        return cls(
            move=mv.move,
            test_id=mv.test_id,
            title=scrub_text(mv.title) or "",
            phase=mv.phase,
            profile=mv.profile,
            wstg=mv.wstg,
            owasp_top10=mv.owasp_top10,
            approval=mv.approval,
            status=mv.status,
            severity=mv.severity,
            grade=mv.grade,
            confidence=mv.confidence,
            evidence=[PublicEvidence.from_internal(e) for e in mv.evidence],
            explanation=scrub_text(mv.explanation),
            ai_explanation=scrub_text(mv.ai_explanation),
            recommendation=scrub_text(mv.recommendation),
            started_at=mv.started_at,
            finished_at=mv.finished_at,
        )


class PublicScope(_Public):
    """Escopo exibido na tela de configuracao (regras de engajamento)."""

    origin: str
    extra_origins: list[str]
    included_paths: list[str]
    excluded_paths: list[str]
    allowed_profiles: list[m.Profile]
    allowed_methods: list[str]
    max_requests_per_second: float
    max_total_requests: int
    window_start: datetime | None = None
    window_end: datetime | None = None
    authorized_by: str
    authorized_at: datetime

    @classmethod
    def from_internal(cls, c: m.CampaignConfig) -> PublicScope:
        return cls(
            origin=sanitize_url(c.origin),
            extra_origins=[sanitize_url(o) for o in c.extra_origins],
            included_paths=c.included_paths,
            excluded_paths=c.excluded_paths,
            allowed_profiles=c.allowed_profiles,
            allowed_methods=c.allowed_methods,
            max_requests_per_second=c.max_requests_per_second,
            max_total_requests=c.max_total_requests,
            window_start=c.window_start,
            window_end=c.window_end,
            authorized_by=scrub_text(c.authorized_by) or "",
            authorized_at=c.authorized_at,
        )


class PublicScore(_Public):
    accuracy: float
    eval_bar: float
    counts: dict[str, int]

    @classmethod
    def from_internal(cls, s: m.Score) -> PublicScore:
        return cls(
            accuracy=s.accuracy,
            eval_bar=s.eval_bar,
            counts={str(k): v for k, v in s.counts.items()},
        )


class PublicCampaign(_Public):
    id: str
    state: m.CampaignState
    created_at: datetime
    finished_at: datetime | None = None
    scope: PublicScope
    score: PublicScore | None = None
    moves: list[PublicMove] = Field(default_factory=list)

    @classmethod
    def from_internal(cls, c: m.Campaign) -> PublicCampaign:
        return cls(
            id=c.id,
            state=c.state,
            created_at=c.created_at,
            finished_at=c.finished_at,
            scope=PublicScope.from_internal(c.config),
            score=PublicScore.from_internal(c.score) if c.score else None,
            moves=[PublicMove.from_internal(x) for x in c.moves],
        )


class PublicEvent(_Public):
    seq: int
    type: m.EventType
    at: datetime
    move: PublicMove | None = None
    # ``data`` e allowlisted por tipo na Plataforma; aqui so escalares saneados.
    data: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @classmethod
    def from_internal(cls, e: m.Event) -> PublicEvent:
        safe: dict[str, Any] = {}
        for k, v in e.data.items():
            if isinstance(v, str):
                safe[k] = scrub_text(v)
            elif isinstance(v, (int, float, bool)) or v is None:
                safe[k] = v
            # tipos complexos (dict/list/objetos) sao descartados de proposito
        return cls(
            seq=e.seq,
            type=e.type,
            at=e.at,
            move=PublicMove.from_internal(e.move) if e.move else None,
            data=safe,
        )


class PublicEventPage(_Public):
    events: list[PublicEvent]
    next_after_seq: int  # cursor para o polling


class PublicAuditEntry(_Public):
    at: datetime
    method: str
    url: str  # sem querystring/userinfo
    allowed: bool
    reason: str | None = None
    status_code: int | None = None
    actor: str

    @classmethod
    def from_internal(cls, a: m.AuditEntry) -> PublicAuditEntry:
        return cls(
            at=a.at,
            method=a.method,
            url=sanitize_url(a.url),
            allowed=a.allowed,
            reason=scrub_text(a.reason),
            status_code=a.status_code,
            actor=scrub_text(a.actor) or "",
        )


class PublicKeyMoment(_Public):
    move: int
    summary: str


class PublicGameReview(_Public):
    campaign: PublicCampaign
    executive_summary: str | None = None
    key_moments: list[PublicKeyMoment] = Field(default_factory=list)
    audit: list[PublicAuditEntry] = Field(default_factory=list)

    @classmethod
    def from_internal(cls, r: m.GameReview) -> PublicGameReview:
        return cls(
            campaign=PublicCampaign.from_internal(r.campaign),
            executive_summary=scrub_text(r.executive_summary),
            key_moments=[
                PublicKeyMoment(move=k.move, summary=scrub_text(k.summary) or "")
                for k in r.key_moments
            ],
            audit=[PublicAuditEntry.from_internal(a) for a in r.audit],
        )


class ApiError(_Public):
    """Erro generico. Nunca traceback, nunca mensagem de excecao interna."""

    code: str  # ex.: out_of_scope, unauthorized, not_found, rate_limited, invalid_request
    message: str


# ------------------------------ entrada ----------------------------------
class _Request(BaseModel):
    """Entradas do front: rejeita campos desconhecidos e limita tamanhos."""

    model_config = ConfigDict(extra="forbid")


class CreateCampaignRequest(_Request):
    origin: str = Field(max_length=300)
    extra_origins: list[str] = Field(default_factory=list, max_length=5)
    included_paths: list[str] = Field(default_factory=lambda: ["/"], max_length=50)
    excluded_paths: list[str] = Field(default_factory=list, max_length=50)
    allowed_profiles: list[m.Profile] = Field(
        default_factory=lambda: [m.Profile.PASSIVE, m.Profile.ACTIVE_LIGHT]
    )
    max_requests_per_second: float = Field(default=2.0, gt=0, le=5)
    max_total_requests: int = Field(default=200, gt=0, le=500)
    window_start: datetime | None = None
    window_end: datetime | None = None
    authorized_by: str = Field(min_length=1, max_length=120)
    # Nota: authorized_at e allowed_methods sao definidos pelo SERVIDOR.
    # O front nao escolhe metodos HTTP; nunca pode liberar POST/PUT/DELETE.


class ApprovalDecisionRequest(_Request):
    decision: m.Approval = Field(description="approved | denied")
    reason: str | None = Field(default=None, max_length=300)


class StopRequest(_Request):
    reason: str | None = Field(default=None, max_length=300)

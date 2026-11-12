"""Rotas FastAPI da Plataforma (Trilho B).

- POST /campaigns .............. cria (403 sincrono se fora de escopo) e inicia
- GET  /campaigns .............. lista
- GET  /campaigns/{id} ......... detalhe (estado + score + lances)
- GET  /campaigns/{id}/moves ... lances
- GET  /campaigns/{id}/events .. eventos (incremental via ?since=)
- POST /campaigns/{id}/stop .... parada de emergencia
- POST /campaigns/{id}/moves/{move}/approve|deny ... fila de aprovacao
- GET  /campaigns/{id}/report .. Game Review (JSON)
- GET  /campaigns/{id}/report/export?format=md|pdf
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.api.context import AppContext, get_ctx
from app.models import (
    Campaign,
    CampaignConfig,
    CampaignState,
    Event,
    GameReview,
    Move,
    Profile,
)
from app.report import PDF_AVAILABLE, to_markdown, to_pdf
from app.sink import ApprovalNotPending

router = APIRouter()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CreateCampaignRequest(BaseModel):
    config: CampaignConfig


class ApprovalResponse(BaseModel):
    campaign_id: str
    move: int
    approval: str


def _preflight_scope(config: CampaignConfig, ctx: AppContext) -> None:
    """Verificacao sincrona minima da Plataforma (403 imediato).

    Nao substitui o Scope Guard do Motor (que valida cada requisicao em
    tempo de execucao); apenas barra pedidos obviamente fora das regras.
    """
    if not config.origin.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=422, detail="origin deve comecar com http:// ou https://"
        )
    if not config.authorized_by.strip():
        raise HTTPException(status_code=403, detail="Teste sem autorizacao registrada.")
    if ctx.settings.block_intrusive and Profile.INTRUSIVE in config.allowed_profiles:
        raise HTTPException(
            status_code=403,
            detail="Perfil 'intrusive' bloqueado por padrao (fora de escopo).",
        )


async def _require_campaign(campaign_id: str, ctx: AppContext) -> Campaign:
    campaign = await ctx.db.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campanha nao encontrada.")
    return campaign


# Tetos impostos pelo SERVIDOR: a tela nao consegue afrouxar as regras.
_SAFE_METHODS = ["GET", "OPTIONS"]
_SAFE_PROFILES = {Profile.PASSIVE, Profile.ACTIVE_LIGHT}
_MAX_RPS = 5.0
_MAX_TOTAL = 500
_MAX_TIMEOUT_S = 30.0


def _enforce_server_limits(config: CampaignConfig) -> CampaignConfig:
    """Mesmo formato de entrada; valores perigosos sao ignorados/limitados."""
    profiles = [p for p in config.allowed_profiles if p in _SAFE_PROFILES] or [Profile.PASSIVE]
    return config.model_copy(
        update={
            "allowed_methods": list(_SAFE_METHODS),
            "allowed_profiles": profiles,
            "max_requests_per_second": min(max(config.max_requests_per_second, 0.1), _MAX_RPS),
            "max_total_requests": min(max(config.max_total_requests, 1), _MAX_TOTAL),
            "request_timeout_s": min(max(config.request_timeout_s, 1.0), _MAX_TIMEOUT_S),
            "authorized_at": config.authorized_at or _now(),
        }
    )


@router.post("/campaigns", response_model=Campaign, status_code=201)
async def create_campaign(
    body: CreateCampaignRequest, ctx: AppContext = Depends(get_ctx)
) -> Campaign:
    _preflight_scope(body.config, ctx)  # 403 sincrono
    config = _enforce_server_limits(body.config)
    campaign = Campaign(
        id=uuid.uuid4().hex,
        config=config,
        state=CampaignState.CREATED,
        created_at=_now(),
    )
    await ctx.db.create_campaign(campaign)
    ctx.launch_campaign(campaign.id, config)
    return campaign


@router.get("/campaigns", response_model=list[Campaign])
async def list_campaigns(ctx: AppContext = Depends(get_ctx)) -> list[Campaign]:
    return await ctx.db.list_campaigns()


@router.get("/campaigns/{campaign_id}", response_model=Campaign)
async def get_campaign(
    campaign_id: str, ctx: AppContext = Depends(get_ctx)
) -> Campaign:
    return await _require_campaign(campaign_id, ctx)


@router.get("/campaigns/{campaign_id}/moves", response_model=list[Move])
async def list_moves(
    campaign_id: str, ctx: AppContext = Depends(get_ctx)
) -> list[Move]:
    await _require_campaign(campaign_id, ctx)
    return await ctx.db.list_moves(campaign_id)


@router.get("/campaigns/{campaign_id}/events", response_model=list[Event])
async def list_events(
    campaign_id: str,
    since: int = Query(0, ge=0, description="Retorna eventos com seq > since"),
    ctx: AppContext = Depends(get_ctx),
) -> list[Event]:
    await _require_campaign(campaign_id, ctx)
    return await ctx.db.list_events(campaign_id, since_seq=since)


@router.post("/campaigns/{campaign_id}/stop", response_model=Campaign)
async def stop_campaign(
    campaign_id: str, ctx: AppContext = Depends(get_ctx)
) -> Campaign:
    await _require_campaign(campaign_id, ctx)
    await ctx.coordinator.request_stop(campaign_id)
    return await _require_campaign(campaign_id, ctx)


@router.post(
    "/campaigns/{campaign_id}/moves/{move}/approve", response_model=ApprovalResponse
)
async def approve_move(
    campaign_id: str,
    move: int,
    actor: str = Query("operator"),
    ctx: AppContext = Depends(get_ctx),
) -> ApprovalResponse:
    return await _resolve(campaign_id, move, True, actor, ctx)


@router.post(
    "/campaigns/{campaign_id}/moves/{move}/deny", response_model=ApprovalResponse
)
async def deny_move(
    campaign_id: str,
    move: int,
    actor: str = Query("operator"),
    ctx: AppContext = Depends(get_ctx),
) -> ApprovalResponse:
    return await _resolve(campaign_id, move, False, actor, ctx)


async def _resolve(
    campaign_id: str, move: int, approved: bool, actor: str, ctx: AppContext
) -> ApprovalResponse:
    await _require_campaign(campaign_id, ctx)
    try:
        decision = await ctx.coordinator.resolve_approval(
            campaign_id, move, approved, actor
        )
    except ApprovalNotPending as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApprovalResponse(
        campaign_id=campaign_id, move=move, approval=decision.value
    )


async def _build_review(campaign_id: str, ctx: AppContext) -> GameReview:
    campaign = await _require_campaign(campaign_id, ctx)
    audit = await ctx.coordinator.audit.history(campaign_id)
    return await ctx.report_builder.build(campaign, audit)


@router.get("/campaigns/{campaign_id}/report", response_model=GameReview)
async def game_review(
    campaign_id: str, ctx: AppContext = Depends(get_ctx)
) -> GameReview:
    return await _build_review(campaign_id, ctx)


@router.get("/campaigns/{campaign_id}/report/export")
async def export_review(
    campaign_id: str,
    format: str = Query("md", pattern="^(md|pdf)$"),
    ctx: AppContext = Depends(get_ctx),
) -> Response:
    review = await _build_review(campaign_id, ctx)
    if format == "md":
        return Response(
            content=to_markdown(review),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="game-review-{campaign_id}.md"'
            },
        )
    if not PDF_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="Exportacao PDF indisponivel: instale 'reportlab'. Use format=md.",
        )
    return Response(
        content=to_pdf(review),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="game-review-{campaign_id}.pdf"'
        },
    )

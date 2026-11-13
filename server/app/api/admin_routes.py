"""Rotas de administracao de escopo (somente admin).

O admin define, pela tela, as URLs autorizadas e os escopos bloqueados. Os
valores ficam no banco (``app_settings``) e no cache ``admin_settings`` que o
``authorization.py`` consulta a cada decisao.

- GET /admin/scope ... valores atuais (admin)
- PUT /admin/scope ... atualiza alvos autorizados e escopos bloqueados (admin)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app import admin_settings
from app.api.context import AppContext, get_ctx
from app.auth import PublicUser, require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


class ScopeSettings(BaseModel):
    authorized_targets: list[str] = Field(
        default_factory=list,
        description="URLs/origens autorizadas. Vazio = nao restringe por esta lista.",
    )
    blocked_scopes: list[str] = Field(
        default_factory=list,
        description="Hosts/origens sempre recusados (em qualquer modo).",
    )


@router.get("/scope", response_model=ScopeSettings)
async def get_admin_scope(_: PublicUser = Depends(require_admin)) -> ScopeSettings:
    return ScopeSettings(
        authorized_targets=admin_settings.authorized_targets(),
        blocked_scopes=admin_settings.blocked_scopes(),
    )


@router.put("/scope", response_model=ScopeSettings)
async def put_admin_scope(
    body: ScopeSettings,
    _: PublicUser = Depends(require_admin),
    ctx: AppContext = Depends(get_ctx),
) -> ScopeSettings:
    cleaned = admin_settings.set_values(body.authorized_targets, body.blocked_scopes)
    await ctx.db.set_setting(admin_settings.AUTHORIZED_KEY, cleaned[admin_settings.AUTHORIZED_KEY])
    await ctx.db.set_setting(admin_settings.BLOCKED_KEY, cleaned[admin_settings.BLOCKED_KEY])
    return ScopeSettings(
        authorized_targets=cleaned[admin_settings.AUTHORIZED_KEY],
        blocked_scopes=cleaned[admin_settings.BLOCKED_KEY],
    )

"""Rotas de autenticacao e gestao de usuarios (cadastro feito pelo sistema).

- POST /auth/login ....... usuario + senha -> token JWT
- GET  /auth/me .......... dados do usuario autenticado
- GET  /auth/users ....... lista usuarios (admin)
- POST /auth/users ....... cria usuario (admin) — nao ha signup aberto
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.context import AppContext, get_ctx
from app.auth import (
    PublicUser,
    TokenResponse,
    create_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=60)
    password: str = Field(min_length=6, max_length=200)
    role: Literal["admin", "operator"] = "operator"


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, ctx: AppContext = Depends(get_ctx)) -> TokenResponse:
    row = await ctx.db.get_user_by_username(body.username.strip())
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario ou senha invalidos.",
        )
    token = create_token(row)
    return TokenResponse(
        access_token=token,
        user=PublicUser(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            created_at=row.get("created_at"),
        ),
    )


@router.get("/me", response_model=PublicUser)
async def me(user: PublicUser = Depends(get_current_user)) -> PublicUser:
    return user


@router.get("/users", response_model=list[PublicUser])
async def list_users(
    _: PublicUser = Depends(require_admin), ctx: AppContext = Depends(get_ctx)
) -> list[PublicUser]:
    rows = await ctx.db.list_users()
    return [
        PublicUser(id=r["id"], username=r["username"], role=r["role"], created_at=r["created_at"])
        for r in rows
    ]


@router.post("/users", response_model=PublicUser, status_code=201)
async def create_user(
    body: CreateUserRequest,
    _: PublicUser = Depends(require_admin),
    ctx: AppContext = Depends(get_ctx),
) -> PublicUser:
    username = body.username.strip()
    if await ctx.db.get_user_by_username(username) is not None:
        raise HTTPException(status_code=409, detail="Usuario ja existe.")
    user_id = uuid.uuid4().hex
    await ctx.db.create_user(user_id, username, hash_password(body.password), body.role)
    row = await ctx.db.get_user_by_username(username)
    assert row is not None
    return PublicUser(
        id=row["id"], username=row["username"], role=row["role"], created_at=row["created_at"]
    )

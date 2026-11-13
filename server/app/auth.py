"""Autenticacao JWT da Plataforma.

- Senhas: hash com ``bcrypt`` (nunca em texto puro no banco).
- Token: JWT HS256 assinado com ``AUTH_SECRET`` (do .env). Sem a variavel, usa
  um segredo de desenvolvimento fixo e AVISA — troque em producao.
- Cadastro e feito pelo SISTEMA: nao ha signup aberto. Um admin inicial e
  semeado no startup (``ADMIN_USERNAME``/``ADMIN_PASSWORD``) e, a partir dai, so
  um admin cria novas contas.

Papeis: ``admin`` (gere escopo e usuarios) e ``operator`` (uso normal).
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

logger = logging.getLogger("pentest_chess.auth")

ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 12
Role = Literal["admin", "operator"]
_DEV_SECRET = "dev-insecure-secret-troque-em-producao"
_warned_secret = False


def _secret() -> str:
    global _warned_secret
    value = (os.getenv("AUTH_SECRET") or "").strip()
    if value:
        return value
    if not _warned_secret:
        logger.warning(
            "AUTH_SECRET nao definido: usando segredo de desenvolvimento. "
            "Defina AUTH_SECRET no .env antes de expor o servidor."
        )
        _warned_secret = True
    return _DEV_SECRET


# --------------------------------------------------------------------- senhas
def hash_password(password: str) -> str:
    # bcrypt limita a 72 bytes; truncamos de forma estavel.
    raw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:72], password_hash.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------- token
class PublicUser(BaseModel):
    id: str
    username: str
    role: Role
    created_at: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: PublicUser


def create_token(user: dict) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["username"],
        "uid": user["id"],
        "role": user["role"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])


# ----------------------------------------------------------------- dependencias
_bearer = HTTPBearer(auto_error=False)
_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Nao autenticado.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> PublicUser:
    if credentials is None or not credentials.credentials:
        raise _UNAUTHORIZED
    try:
        payload = decode_token(credentials.credentials)
    except jwt.PyJWTError as exc:  # expirado/invalido
        raise _UNAUTHORIZED from exc
    username = payload.get("sub")
    if not username:
        raise _UNAUTHORIZED
    row = await request.app.state.ctx.db.get_user_by_username(username)
    if row is None:
        raise _UNAUTHORIZED
    return PublicUser(
        id=row["id"],
        username=row["username"],
        role=row["role"],
        created_at=row.get("created_at"),
    )


async def require_admin(user: PublicUser = Depends(get_current_user)) -> PublicUser:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acao restrita a administradores.",
        )
    return user


# ------------------------------------------------------------------- seeding
async def ensure_seed_admin(db) -> None:
    """Cria o admin inicial se ainda nao houver nenhum usuario."""
    if await db.count_users() > 0:
        return
    username = (os.getenv("ADMIN_USERNAME") or "admin").strip() or "admin"
    password = os.getenv("ADMIN_PASSWORD") or "admin"
    await db.create_user(uuid.uuid4().hex, username, hash_password(password), "admin")
    logger.warning(
        "Admin inicial criado (usuario=%r). Troque a senha e defina "
        "ADMIN_USERNAME/ADMIN_PASSWORD no .env.",
        username,
    )

"""Lista de alvos AUTORIZADOS, definida no servidor (nunca pela tela/usuario).

    .env:  AUTHORIZED_TARGETS=https://alvo-do-hackathon.com,http://127.0.0.1:8080

Sem a variavel, so enderecos locais (127.0.0.1 / localhost) sao aceitos: o
site de treino funciona, a internet nao. Testar sem autorizacao e crime
(art. 154-A do Codigo Penal).
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit

from app.engine.scope import normalize_origin

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def authorized_origins() -> set[str]:
    raw = os.getenv("AUTHORIZED_TARGETS", "")
    return {o for o in (normalize_origin(x) for x in raw.split(",") if x.strip()) if o}


def is_authorized(url: str) -> bool:
    origin = normalize_origin(url)
    if origin is None:
        return False
    allowed = authorized_origins()
    if allowed:
        return origin in allowed
    return (urlsplit(url).hostname or "").lower() in _LOCAL_HOSTS


def explain_refusal(url: str) -> str:
    allowed = sorted(authorized_origins())
    lista = ", ".join(allowed) if allowed else "somente enderecos locais (127.0.0.1)"
    return f"Alvo {url} NAO esta autorizado. Autorizados: {lista}. Ajuste AUTHORIZED_TARGETS no .env."

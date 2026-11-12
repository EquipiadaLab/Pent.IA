"""Mascaramento de segredos e trilha de auditoria (Trilho B).

Regra de ouro do dossie: segredos/cookies sao mascarados ANTES de gravar
evidencia ou auditoria, e NUNCA entram em prompt de LLM.

Este modulo e puro (funcoes de mascaramento) + um helper que grava a
``AuditEntry`` ja higienizada no banco.
"""

from __future__ import annotations

import re

from app.db import Database
from app.models import AuditEntry, Evidence

MASK = "***"

# Cabecalhos cujo VALOR e sempre sensivel.
_SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "x-amz-security-token",
    "x-csrf-token",
    "api-key",
}

# Padroes de segredo embutidos em texto livre.
_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)\bbasic\s+[A-Za-z0-9+/=]+"),
    # JWT (tres segmentos base64url separados por ponto)
    re.compile(r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
    # chaves tipo AWS access key id
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    # pares chave=segredo (token, secret, password, apikey...)
    re.compile(
        r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd|access[_-]?key|client[_-]?secret)\b\s*[=:]\s*\S+"
    ),
]


def mask_text(value: str | None) -> str | None:
    """Mascara segredos conhecidos dentro de um texto livre."""
    if not value:
        return value
    out = value
    for pat in _PATTERNS:
        if pat.pattern.endswith(r"\S+"):
            out = pat.sub(lambda m: f"{m.group(1)}={MASK}", out)
        else:
            out = pat.sub(MASK, out)
    return out


def mask_cookie_value(raw: str) -> str:
    """Preserva o NOME do cookie e seus atributos (HttpOnly, Secure...),
    mascarando so o valor. Ex.: ``sid=abc123; HttpOnly`` -> ``sid=***; HttpOnly``."""
    parts = [p.strip() for p in raw.split(";")]
    if not parts:
        return MASK
    first = parts[0]
    if "=" in first:
        name, _, _ = first.partition("=")
        parts[0] = f"{name}={MASK}"
    else:
        parts[0] = MASK
    return "; ".join(parts)


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    """Devolve uma copia dos cabecalhos com valores sensiveis mascarados."""
    masked: dict[str, str] = {}
    for key, value in headers.items():
        low = key.lower()
        if low in {"cookie", "set-cookie"}:
            masked[key] = mask_cookie_value(value)
        elif low in _SENSITIVE_HEADERS:
            masked[key] = MASK
        else:
            masked[key] = mask_text(value) or value
    return masked


def mask_evidence(ev: Evidence) -> Evidence:
    """Higieniza uma evidencia (defesa em profundidade: o Motor ja deve
    mandar mascarado, mas a Plataforma nao confia e remascara)."""
    return ev.model_copy(
        update={
            "request": mask_text(ev.request) or ev.request,
            "response_headers": mask_headers(ev.response_headers),
            "note": mask_text(ev.note),
        }
    )


def mask_audit_entry(entry: AuditEntry) -> AuditEntry:
    return entry.model_copy(
        update={
            "url": mask_text(entry.url) or entry.url,
            "reason": mask_text(entry.reason),
        }
    )


class AuditTrail:
    """Grava entradas de auditoria sempre higienizadas (append-only)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def record(self, entry: AuditEntry) -> None:
        await self._db.append_audit(mask_audit_entry(entry))

    async def history(self, campaign_id: str) -> list[AuditEntry]:
        return await self._db.list_audit(campaign_id)

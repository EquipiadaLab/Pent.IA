"""Mascaramento/saneamento. Fonte unica de verdade para "o que pode sair".

Usado em DOIS pontos (defesa em profundidade):
  1. Plataforma, ANTES de gravar evidencia/auditoria no banco e antes de
     mandar qualquer coisa a um LLM.
  2. Fronteira da API, ao montar os schemas publicos.

Regra: allowlist, nunca blocklist. O que nao esta listado nao sai.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit

# Unicos cabecalhos de resposta que podem aparecer na evidencia.
SAFE_HEADERS: frozenset[str] = frozenset(
    {
        "strict-transport-security",
        "content-security-policy",
        "content-security-policy-report-only",
        "x-frame-options",
        "x-content-type-options",
        "referrer-policy",
        "permissions-policy",
        "x-xss-protection",
        "access-control-allow-origin",
        "access-control-allow-credentials",
        "access-control-allow-methods",
        "access-control-allow-headers",
        "allow",
        "server",
        "x-powered-by",
        "content-type",
        "cache-control",
        "location",
        "set-cookie",
    }
)

MAX_HEADER_VALUE = 500
MAX_TEXT = 4000

# Padroes de segredo que nunca devem aparecer em texto livre.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"(?i)aws_secret_access_key\s*[=:]\s*\S+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"),  # JWT
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd)\s*[=:]\s*\S+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def scrub_text(text: str | None) -> str | None:
    """Remove segredos conhecidos de texto livre e limita o tamanho."""
    if text is None:
        return None
    for pat in _SECRET_PATTERNS:
        text = pat.sub("***", text)
    return text[:MAX_TEXT]


def sanitize_url(url: str) -> str:
    """Remove userinfo, query string e fragmento (podem carregar tokens)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "***"
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def mask_set_cookie(value: str) -> str:
    """``sid=abc123; HttpOnly; Secure`` -> ``sid=***; HttpOnly; Secure``.

    Mantem nome e flags (o que o teste avalia); esconde o valor."""
    head, _, rest = value.partition(";")
    name, eq, _val = head.partition("=")
    masked = f"{name.strip()}=***" if eq else name.strip()
    return f"{masked};{rest}" if rest else masked


def sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    """Allowlist de cabecalhos + mascaramento de valores sensiveis."""
    out: dict[str, str] = {}
    for key, value in headers.items():
        k = key.lower()
        if k not in SAFE_HEADERS:
            continue
        if k == "set-cookie":
            value = mask_set_cookie(value)
        elif k == "location":
            value = sanitize_url(value)
        out[k] = (scrub_text(value) or "")[:MAX_HEADER_VALUE]
    return out

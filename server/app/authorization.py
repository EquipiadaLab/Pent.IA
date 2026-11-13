"""Controle de alvo da campanha.

Dois modos:

1. LISTA FIXA (opcional) — se ``AUTHORIZED_TARGETS`` estiver no .env, so os
   alvos dessa lista sao aceitos. Modo mais restrito, para travar o escopo.

2. ABERTO (padrao) — sem ``AUTHORIZED_TARGETS``, a aplicacao aceita qualquer
   URL que o front enviar (o operador declara o alvo e assume a autorizacao).
   Mesmo aberto, continuam valendo tres protecoes NAO negociaveis:
     - cada campanha fica presa a UM alvo (o motor nao segue redirecionamento
       para fora da origem);
     - enderecos internos/privados sao BLOQUEADOS (anti-SSRF): rede interna,
       localhost de outros servicos e o endpoint de metadados da nuvem
       (169.254.169.254) nunca podem ser alvo — senao a ferramenta viraria
       uma forma de ler as credenciais do proprio servidor;
     - tudo fica na trilha de auditoria, com quem autorizou.

Quando o front nao envia alvo, usa-se ``DEFAULT_TARGET`` (padrao: migbot).

Testar sem autorizacao do titular e crime (art. 154-A do Codigo Penal): o
campo ``authorized_by`` registra quem assumiu essa responsabilidade.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlsplit

from app import admin_settings
from app.engine.scope import normalize_origin

_DEFAULT_TARGET_FALLBACK = "https://3.migbot.com.br"
_LOOPBACK_NAMES = {"localhost"}


# ---------------------------------------------------------------- config
def default_target() -> str:
    raw = (os.getenv("DEFAULT_TARGET") or "").strip() or _DEFAULT_TARGET_FALLBACK
    if "://" not in raw:
        raw = "https://" + raw
    return raw


def locked_target() -> str | None:
    """Alvo UNICO travado. Se ``LOCKED_TARGET`` estiver no .env, o sistema so
    testa esse endereco: qualquer outra URL enviada pelo front e recusada, e
    origin vazio usa este alvo. E a trava mais forte (acima da lista)."""
    raw = (os.getenv("LOCKED_TARGET") or "").strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = "https://" + raw
    return raw


def authorized_origins() -> set[str]:
    """Alvos autorizados: uniao do ``.env`` (AUTHORIZED_TARGETS) com os que o
    admin cadastrou pela tela (``admin_settings``)."""
    raw = os.getenv("AUTHORIZED_TARGETS", "")
    from_env = (normalize_origin(x) for x in raw.split(",") if x.strip())
    from_admin = (normalize_origin(x) for x in admin_settings.authorized_targets())
    return {o for o in (*from_env, *from_admin) if o}


def blocked_scopes() -> list[str]:
    """Hosts/origens que o admin bloqueou (recusados em qualquer modo)."""
    return admin_settings.blocked_scopes()


def _is_blocked_scope(url: str) -> str | None:
    """Motivo do bloqueio se o alvo casar com um escopo bloqueado pelo admin."""
    origin = normalize_origin(url)
    host = (urlsplit(url).hostname or "").lower()
    for raw in blocked_scopes():
        entry = raw.strip().lower()
        if not entry:
            continue
        entry_origin = normalize_origin(raw)
        entry_host = (urlsplit(raw if "://" in raw else f"//{raw}").hostname or entry).lower()
        if entry_origin and origin and entry_origin == origin:
            return f"Alvo {origin} esta em um escopo bloqueado pelo admin."
        if host and entry_host and (host == entry_host or host.endswith("." + entry_host)):
            return f"Host {host} esta em um escopo bloqueado pelo admin."
    return None


def accepts_any_target() -> bool:
    """True = modo aberto (sem alvo travado e sem lista fixa)."""
    return locked_target() is None and not authorized_origins()


def _block_private() -> bool:
    return os.getenv("BLOCK_PRIVATE_TARGETS", "true").strip().lower() not in ("0", "false", "no", "nao")


# ---------------------------------------------------------------- anti-SSRF
def _host_is_loopback(host: str) -> bool:
    h = host.lower().strip("[]")
    if h in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


def _blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # loopback e permitido (site de treino); o resto da rede interna, nao.
    if ip.is_loopback:
        return False
    return ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified


def _resolve_blocked(host: str) -> str | None:
    """Resolve o host e bloqueia se apontar para rede interna/privada.
    Retorna o motivo do bloqueio, ou None se estiver liberado."""
    if _host_is_loopback(host):
        return None  # site de treino local
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return "nao foi possivel resolver o endereco"
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _blocked_ip(ip):
            return f"o endereco aponta para uma rede interna/privada ({ip}), bloqueado por seguranca"
    return None


# ---------------------------------------------------------------- decisao
def authorization_error(url: str) -> str | None:
    """None = alvo liberado. Texto = motivo da recusa."""
    origin = normalize_origin(url)
    if origin is None:
        return "URL invalida (use http:// ou https:// com host valido)."

    # Escopos bloqueados pelo admin valem em QUALQUER modo (acima do resto).
    blocked = _is_blocked_scope(url)
    if blocked:
        return blocked

    locked = locked_target()
    if locked:  # trava mais forte: so o alvo travado passa
        if normalize_origin(locked) == origin:
            return None
        return f"Alvo travado: este sistema so testa {locked}."

    allowed = authorized_origins()
    if allowed:  # modo lista fixa
        if origin in allowed:
            return None
        return f"Alvo {origin} fora da lista autorizada ({', '.join(sorted(allowed))})."

    # modo aberto: bloqueia so rede interna/privada
    if _block_private():
        host = urlsplit(url).hostname or ""
        reason = _resolve_blocked(host)
        if reason:
            return f"Alvo {origin} recusado: {reason}."
    return None


def is_authorized(url: str) -> bool:
    return authorization_error(url) is None


def explain_refusal(url: str) -> str:
    return authorization_error(url) or f"Alvo {url} recusado."

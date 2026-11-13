"""Scope Guard: o limite e imposto pelo SISTEMA, em cada requisicao.

Nada aqui depende de boa vontade do agente nem do LLM. Toda requisicao do
Motor passa por ``ScopeGuard.authorize`` antes de sair.
"""

from __future__ import annotations

import asyncio
import posixpath
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import unquote, urlsplit

from app.models import CampaignConfig, Profile

_DEFAULT_PORTS = {"http": 80, "https": 443}


def utcnow() -> datetime:
    return datetime.now(UTC)


def normalize_origin(url: str) -> str | None:
    """``https://Alvo.com`` e ``https://alvo.com:443`` -> ``https://alvo.com:443``.

    Normaliza porta padrao dos DOIS lados (corrige o problema #10 do dossie)."""
    try:
        parts = urlsplit(url.strip())
        scheme = (parts.scheme or "").lower()
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if scheme not in _DEFAULT_PORTS or not host:
        return None
    if ":" in host:  # IPv6
        host = f"[{host}]"
    return f"{scheme}://{host.lower()}:{port or _DEFAULT_PORTS[scheme]}"


def canonical_path(path: str) -> str:
    """Decodifica e resolve ``..`` para impedir burlar rotas excluidas."""
    path = unquote(path or "/")
    if not path.startswith("/"):
        path = "/" + path
    canon = posixpath.normpath(path)
    return "/" + canon.lstrip("/") if canon.startswith("//") else canon


def _path_matches(path: str, prefix: str) -> bool:
    prefix = canonical_path(prefix)
    if prefix == "/":
        return True
    return path == prefix or path.startswith(prefix.rstrip("/") + "/")


@dataclass(frozen=True)
class ScopeDecision:
    allowed: bool
    reason: str | None = None


# Exceção estreita e documentada: o UNICO par (metodo, caminho exato) fora de
# GET/OPTIONS que o Scope Guard pode autorizar, e so para o check de
# Credential Access (CREDS-SQLI-LOGIN-001). Nao e uma liberacao geral de
# metodos de escrita -- qualquer outra combinacao continua bloqueada.
_EXTRA_METHOD_ALLOWLIST: frozenset[tuple[str, str]] = frozenset({("POST", "/rest/user/login")})


class ScopeGuard:
    def __init__(self, config: CampaignConfig) -> None:
        self.config = config
        origins = [normalize_origin(config.origin)]
        origins += [normalize_origin(o) for o in config.extra_origins]
        self._origins = {o for o in origins if o}
        self._methods = {m.upper() for m in config.allowed_methods}
        self._requests = 0
        self._last = 0.0
        self._lock = asyncio.Lock()

    # -- consultas puras -----------------------------------------------------
    def origin_in_scope(self, url: str) -> bool:
        origin = normalize_origin(url)
        return origin is not None and origin in self._origins

    def window_ok(self, now: datetime | None = None) -> ScopeDecision:
        now = now or utcnow()
        for bound, is_start in ((self.config.window_start, True), (self.config.window_end, False)):
            if bound is None:
                continue
            if bound.tzinfo is None:
                bound = bound.replace(tzinfo=UTC)
            if (is_start and now < bound) or (not is_start and now > bound):
                return ScopeDecision(False, "fora da janela de execucao autorizada")
        return ScopeDecision(True)

    @property
    def requests_made(self) -> int:
        return self._requests

    # -- decisao por requisicao ---------------------------------------------
    def authorize(self, method: str, url: str, profile: Profile = Profile.PASSIVE) -> ScopeDecision:
        """Decide e, se permitido, CONTA a requisicao no teto da campanha."""
        decision = self._check(method, url, profile)
        if decision.allowed:
            self._requests += 1
        return decision

    def _check(self, method: str, url: str, profile: Profile) -> ScopeDecision:
        try:
            parts = urlsplit(url)
        except ValueError:
            return ScopeDecision(False, "URL invalida")
        if parts.username or parts.password:
            return ScopeDecision(False, "URL com credenciais embutidas")
        verb = method.upper()
        is_login_exception = (verb, canonical_path(parts.path)) in _EXTRA_METHOD_ALLOWLIST
        if verb not in self._methods and not is_login_exception:
            return ScopeDecision(False, f"metodo {verb} nao permitido")
        if not self.origin_in_scope(url):
            return ScopeDecision(False, "origem fora do escopo autorizado")
        if profile not in self.config.allowed_profiles:
            return ScopeDecision(False, f"perfil {profile.value} nao permitido")
        window = self.window_ok()
        if not window.allowed:
            return window
        if self._requests >= self.config.max_total_requests:
            return ScopeDecision(False, "limite total de requisicoes atingido")
        path = canonical_path(parts.path)
        for excluded in self.config.excluded_paths:
            if _path_matches(path, excluded):
                return ScopeDecision(False, "rota excluida do escopo")
        if not any(_path_matches(path, inc) for inc in self.config.included_paths):
            return ScopeDecision(False, "rota fora das incluidas no escopo")
        return ScopeDecision(True)

    async def throttle(self) -> None:
        """Limite de taxa (protege contra derrubar o alvo, art. 266 CP)."""
        interval = 1.0 / max(self.config.max_requests_per_second, 0.1)
        async with self._lock:
            wait = self._last + interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()

"""Tipos base do catalogo de lances (catalogo FECHADO: nada e gerado em runtime)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

import httpx

from app.engine.executor import FetchResult, Fetcher
from app.engine.scope import ScopeGuard, normalize_origin
from app.models import CampaignConfig, Confidence, Evidence, Phase, Profile, Severity, Status

_REDIRECTS = {301, 302, 303, 307, 308}
MAX_HOPS = 3


@dataclass
class CheckOutcome:
    status: Status
    explanation: str
    recommendation: str | None = None
    severity: Severity | None = None  # sobrescreve o default do spec
    confidence: Confidence = Confidence.HIGH
    evidence: list[Evidence] = field(default_factory=list)
    exemplary: bool = False  # defesa acima do padrao -> brilliant/great


CheckFn = Callable[["CheckContext"], Awaitable[CheckOutcome]]


@dataclass(frozen=True)
class CheckSpec:
    test_id: str
    title: str
    phase: Phase
    profile: Profile
    severity: Severity
    wstg: str
    owasp: str
    fn: CheckFn
    needs_approval: bool = False
    hypothesis: str = ""  # hipotese padrao (reserva se a IA nao planejar)
    expected: str = ""  # resultado esperado de um site seguro
    impact: str = ""  # impacto se o problema existir


class CheckContext:
    """Estado compartilhado de UMA campanha para os checks."""

    def __init__(self, config: CampaignConfig, fetcher: Fetcher, guard: ScopeGuard,
                 *, replay: bool = False) -> None:
        self.config = config
        self.fetcher = fetcher
        self.guard = guard
        self.origin = config.origin.rstrip("/")
        self.move_no = 0
        # replay = segunda observacao para confirmar um achado: requisicoes novas,
        # evidencias proprias (ev-N-101, ev-N-102...) e sem reaproveitar cache.
        self.replay = replay
        self._ev = 100 if replay else 0
        self._base: FetchResult | None = None

    # -- evidencias --------------------------------------------------------
    def next_ev_id(self) -> str:
        self._ev += 1
        return f"ev-{self.move_no}-{self._ev}"

    def note_evidence(self, request: str, note: str) -> Evidence:
        return Evidence(id=self.next_ev_id(), request=request, note=note)

    # -- requisicoes -------------------------------------------------------
    async def get(self, path: str, *, profile: Profile = Profile.PASSIVE, method: str = "GET",
                  headers: dict[str, str] | None = None, note: str | None = None,
                  origin: str | None = None) -> FetchResult:
        url = (origin or self.origin).rstrip("/") + path
        return await self.fetcher.request(method, url, profile=profile, ev_id=self.next_ev_id(),
                                          headers=headers, note=note)

    async def base(self) -> FetchResult:
        """GET / uma unica vez; segue redirects SO dentro da mesma origem (max 3)."""
        if self._base is not None:
            return self._base
        saved = self.move_no
        if not self.replay:
            self.move_no = 0  # evidencia compartilhada entre lances: ev-0-*
        url = self.origin + "/"
        result = await self.fetcher.request("GET", url, profile=Profile.PASSIVE, ev_id=self.next_ev_id())
        for _ in range(MAX_HOPS):
            resp = result.response
            if resp is None or resp.status_code not in _REDIRECTS:
                break
            loc = resp.headers.get("location")
            target = urljoin(url, loc) if loc else None
            if not target or normalize_origin(target) != normalize_origin(url):
                break
            url = target
            result = await self.fetcher.request("GET", url, profile=Profile.PASSIVE, ev_id=self.next_ev_id())
        self.move_no = saved
        self._base = result
        return result

    @property
    def base_response(self) -> httpx.Response | None:
        return self._base.response if self._base is not None else None

    @property
    def base_failed(self) -> bool:
        return self._base is not None and not self._base.ok

    @property
    def scheme(self) -> str:
        return urlsplit(self.origin).scheme.lower()


def header(resp: httpx.Response, name: str) -> str | None:
    return resp.headers.get(name)


async def need_base(ctx: CheckContext) -> tuple[httpx.Response | None, FetchResult, CheckOutcome | None]:
    """Resposta-base utilizavel para checks de cabecalho, ou o resultado inconclusivo."""
    base = await ctx.base()
    ev = [base.evidence] if base.evidence else []
    if not base.ok:
        return None, base, CheckOutcome(Status.INCONCLUSIVE, f"Sem resposta do alvo ({base.error}).",
                                        "Verificar disponibilidade do alvo.", confidence=Confidence.LOW)
    if base.response.status_code in _REDIRECTS:
        return None, base, CheckOutcome(
            Status.INCONCLUSIVE, "A raiz redireciona para fora do escopo; cabecalhos nao avaliados.",
            "Incluir o destino do redirecionamento no escopo.", confidence=Confidence.LOW, evidence=ev)
    return base.response, base, None

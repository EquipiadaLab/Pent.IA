"""Executor HTTP: unico lugar do Motor que fala com a rede.

Garantias (cada requisicao, nao so na entrada da campanha):
  parada de emergencia -> Scope Guard -> rate limit -> request -> auditoria.
Falhas de rede (TLS invalido, timeout) viram RESULTADO, nunca derrubam a campanha.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from app.interfaces import EventSink
from app.models import AuditEntry, CampaignConfig, Event, EventType, Evidence, Profile
from app.engine.scope import ScopeGuard, utcnow
from app.redact import sanitize_headers, sanitize_url

USER_AGENT = "PentestChess/0.1 (authorized assessment)"


@dataclass
class FetchResult:
    url: str
    response: httpx.Response | None = None
    evidence: Evidence | None = None
    error: str | None = None  # blocked | stopped | tls | timeout | connect | network

    @property
    def ok(self) -> bool:
        return self.response is not None


def classify_error(exc: Exception) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    text = str(exc).upper()
    if isinstance(exc, httpx.ConnectError):
        return "tls" if ("CERTIFICATE" in text or "SSL" in text) else "connect"
    return "network"


def build_evidence(ev_id: str, method: str, url: str, resp: httpx.Response, note: str | None = None) -> Evidence:
    """Evidencia ja MASCARADA (headers por allowlist, cookies sem valor, sem corpo)."""
    headers: dict[str, str] = {}
    for key, value in resp.headers.multi_items():
        k = key.lower()
        headers[k] = f"{headers[k]}\n{value}" if k == "set-cookie" and k in headers else value
    path = urlsplit(sanitize_url(url)).path or "/"
    return Evidence(
        id=ev_id,
        request=f"{method} {path} HTTP/1.1",
        response_status=resp.status_code,
        response_headers=sanitize_headers(headers),
        response_sha256=hashlib.sha256(resp.content).hexdigest(),
        note=note,
    )


class Fetcher:
    def __init__(self, campaign_id: str, config: CampaignConfig, sink: EventSink, guard: ScopeGuard) -> None:
        self.campaign_id = campaign_id
        self.sink = sink
        self.guard = guard
        self.client = httpx.AsyncClient(
            follow_redirects=False,  # redirecionamento fora do escopo nunca e seguido
            trust_env=False,  # ignora proxies/env do host
            verify=True,
            timeout=config.request_timeout_s,
            headers={"User-Agent": USER_AGENT},
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        profile: Profile,
        ev_id: str,
        headers: dict[str, str] | None = None,
        note: str | None = None,
        json_body: dict | None = None,
    ) -> FetchResult:
        if await self.sink.should_stop():
            return FetchResult(url, error="stopped")

        decision = self.guard.authorize(method, url, profile)
        if not decision.allowed:
            await self.sink.audit(
                AuditEntry(campaign_id=self.campaign_id, at=utcnow(), method=method.upper(),
                           url=sanitize_url(url), allowed=False, reason=decision.reason)
            )
            await self.sink.emit(
                Event(campaign_id=self.campaign_id, type=EventType.SCOPE_BLOCKED, at=utcnow(),
                      data={"method": method.upper(), "url": sanitize_url(url), "reason": decision.reason})
            )
            return FetchResult(url, error="blocked")

        await self.guard.throttle()
        try:
            resp = await self.client.request(method, url, headers=headers, json=json_body)
        except Exception as exc:  # noqa: BLE001 - falha de rede vira resultado
            kind = classify_error(exc)
            await self.sink.audit(
                AuditEntry(campaign_id=self.campaign_id, at=utcnow(), method=method.upper(),
                           url=sanitize_url(url), allowed=True, reason=f"falha: {kind}")
            )
            return FetchResult(url, error=kind)

        evidence = build_evidence(ev_id, method.upper(), url, resp, note)
        await self.sink.audit(
            AuditEntry(campaign_id=self.campaign_id, at=utcnow(), method=method.upper(),
                       url=sanitize_url(url), allowed=True, status_code=resp.status_code,
                       response_sha256=evidence.response_sha256)
        )
        return FetchResult(url, response=resp, evidence=evidence)

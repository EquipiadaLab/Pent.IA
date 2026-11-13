"""Correlacao de achados com CVEs publicos (NVD). Sem chamadas reais a rede."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app.cve.correlation import correlate_campaign
from app.cve.models import CveMatch, CveReference, ExploitReference
from app.cve.nvd_client import NvdClient, build_search_term
from app.models import Campaign, CampaignConfig, Evidence, Move, Phase, Profile, Severity, Status
from app.report import to_markdown
from app.models import GameReview


def _campaign_with_header(server: str | None, powered_by: str | None = None) -> Campaign:
    headers = {}
    if server:
        headers["server"] = server
    if powered_by:
        headers["x-powered-by"] = powered_by
    move = Move(
        move=1, test_id="INFO-001", title="Exposicao de versao do servidor",
        phase=Phase.OPENING, profile=Profile.PASSIVE, status=Status.WARNING, severity=Severity.LOW,
        evidence=[Evidence(id="ev-1-1", request="GET / HTTP/1.1", response_status=200, response_headers=headers)],
    )
    return Campaign(
        id="camp-cve", config=CampaignConfig(origin="https://alvo.exemplo", authorized_by="x",
                                             authorized_at=datetime.now(timezone.utc)),
        created_at=datetime.now(timezone.utc), moves=[move],
    )


def test_build_search_term_strips_comment_and_uses_observed_value():
    assert build_search_term("nginx/1.14.0 (Ubuntu)", None) == "nginx/1.14.0"
    assert build_search_term(None, "Express") == "Express"
    assert build_search_term(None, None) is None
    assert build_search_term("  ", "") is None


def test_build_search_term_ignores_cdn_proxy_names():
    """CDN/proxy nao e o software de origem; correlacionar por ele seria enganoso."""
    assert build_search_term("cloudflare", None) is None
    assert build_search_term("cloudflare", "Express") == "Express"  # usa o outro header valido
    assert build_search_term("AkamaiGHost", None) is None


class _FakeNvdClient(NvdClient):
    """Substitui a chamada HTTP real por um resultado fixo e conhecido."""

    def __init__(self, result: CveMatch | Exception):
        super().__init__()
        self._result = result

    async def search_by_keyword(self, term: str, *, move: int | None = None) -> CveMatch:
        if isinstance(self._result, Exception):
            return CveMatch(search_term=term, move=move, queried_at="2026-01-01T00:00:00Z", error="RuntimeError")
        return self._result.model_copy(update={"search_term": term, "move": move})


def test_correlate_campaign_extracts_term_from_evidence_and_queries_once():
    campaign = _campaign_with_header("nginx/1.14.0", "Express")
    fake_match = CveMatch(
        search_term="nginx/1.14.0", queried_at="2026-01-01T00:00:00Z",
        cves=[CveReference(cve_id="CVE-2024-0001", description="desc", cvss_score=9.8,
                           cvss_severity="CRITICAL", nvd_url="https://nvd.nist.gov/vuln/detail/CVE-2024-0001",
                           exploits=[ExploitReference(url="https://github.com/x/poc", source="github.com")])],
    )
    client = _FakeNvdClient(fake_match)

    matches = asyncio.run(correlate_campaign(campaign, client))

    assert len(matches) == 1
    assert matches[0].search_term == "nginx/1.14.0"
    assert matches[0].move == 1
    assert matches[0].cves[0].cve_id == "CVE-2024-0001"
    assert matches[0].cves[0].exploits[0].url == "https://github.com/x/poc"


def test_correlate_campaign_without_technology_header_returns_empty():
    campaign = _campaign_with_header(None, None)
    client = _FakeNvdClient(CveMatch(search_term="x", queried_at="2026-01-01T00:00:00Z"))

    matches = asyncio.run(correlate_campaign(campaign, client))

    assert matches == []


def test_correlate_campaign_survives_nvd_failure():
    campaign = _campaign_with_header("nginx/1.14.0")
    client = _FakeNvdClient(RuntimeError("boom"))

    matches = asyncio.run(correlate_campaign(campaign, client))

    assert len(matches) == 1
    assert matches[0].error == "RuntimeError"
    assert matches[0].cves == []


def test_markdown_includes_cve_section_with_exploit_link():
    campaign = _campaign_with_header("nginx/1.14.0")
    review = GameReview(campaign=campaign, executive_summary="resumo")
    matches = [
        CveMatch(
            search_term="nginx/1.14.0", move=1, queried_at="2026-01-01T00:00:00Z",
            cves=[CveReference(cve_id="CVE-2024-0001", description="desc", cvss_score=9.8,
                               cvss_severity="CRITICAL", nvd_url="https://nvd.nist.gov/vuln/detail/CVE-2024-0001",
                               exploits=[ExploitReference(url="https://github.com/x/poc")])],
        )
    ]

    md = to_markdown(review, matches)

    assert "CVEs e exploits conhecidos" in md
    assert "CVE-2024-0001" in md
    assert "github.com/x/poc" in md


def test_markdown_without_cve_matches_explains_why():
    campaign = _campaign_with_header(None, None)
    review = GameReview(campaign=campaign, executive_summary="resumo")

    md = to_markdown(review, [])

    assert "Nenhuma tecnologia com versao identificavel" in md


@pytest.mark.asyncio
async def test_nvd_client_caches_result_for_same_term(monkeypatch):
    client = NvdClient()
    calls = {"n": 0}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            calls["n"] += 1
            return {"vulnerabilities": []}

    class FakeHttpClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", lambda **k: FakeHttpClient())

    await client.search_by_keyword("nginx")
    await client.search_by_keyword("nginx")

    assert calls["n"] == 1  # segunda chamada veio do cache

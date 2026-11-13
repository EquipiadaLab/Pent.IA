"""Cliente da API publica do NIST NVD 2.0 (https://nvd.nist.gov/developers/vulnerabilities).

Sem chave de API: limite de 5 requisicoes / 30s (documentado pelo NVD). Com
``NVD_API_KEY`` no .env: 50 / 30s. O cliente nunca bloqueia o relatorio por
muito tempo (timeout curto) e nunca propaga excecao: falha de rede ou da NVD
vira ``CveMatch.error``, nao quebra a geracao do relatorio.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

import httpx

from app.cve.models import CveMatch, CveReference, ExploitReference

logger = logging.getLogger("pentest_chess.cve")

NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
_DEFAULT_TIMEOUT_S = 20.0
_MAX_CVES_PER_TERM = 5
_CACHE_TTL_S = 3600.0  # 1h: suficiente para uma sessao de demo, evita rate limit


# CDNs/proxies reversos: o header Server deles descreve a borda de rede, nao
# o software de origem por tras. Correlacionar CVE a partir desse nome geraria
# resultados enganosos (ex.: CVEs de produtos nao relacionados ao alvo real).
_CDN_PROXY_NAMES = frozenset({"cloudflare", "akamaighost", "akamai", "fastly", "varnish", "sucuri/cloudproxy"})


def build_search_term(server_header: str | None, powered_by: str | None) -> str | None:
    """Extrai um termo de busca SOMENTE do que foi observado de verdade.

    Nao inventa versao nem produto: se o cabecalho nao tiver um numero de
    versao reconhecivel, retorna o texto como esta (ex.: "nginx"), que ainda
    e uma busca legitima por produto, so menos especifica. CDNs/proxies
    conhecidos (ver ``_CDN_PROXY_NAMES``) sao ignorados: eles descrevem a
    borda de rede, nao o software de origem, e correlacionar por esse nome
    produziria CVEs de produtos nao relacionados ao alvo real.
    """
    for raw in (server_header, powered_by):
        candidate = (raw or "").strip()
        if not candidate:
            continue
        # Remove comentarios tipo "(Ubuntu)" que poluem a busca por palavra-chave.
        candidate = re.sub(r"\s*\([^)]*\)", "", candidate).strip()
        if candidate and candidate.lower() not in _CDN_PROXY_NAMES:
            return candidate
    return None


def _severity_from_metrics(metrics: dict) -> tuple[float | None, str | None, str | None]:
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key)
        if entries:
            data = entries[0].get("cvssData", {})
            score = data.get("baseScore")
            severity = data.get("baseSeverity") or entries[0].get("baseSeverity")
            vector = data.get("vectorString")
            return score, severity, vector
    return None, None, None


def _parse_cve(raw: dict) -> CveReference:
    cve = raw["cve"]
    cve_id = cve["id"]
    description = next(
        (d["value"] for d in cve.get("descriptions", []) if d.get("lang") == "en"),
        "Sem descricao em ingles disponivel.",
    )
    score, severity, vector = _severity_from_metrics(cve.get("metrics", {}))
    cwe_ids = sorted(
        {
            w["description"][0]["value"]
            for w in cve.get("weaknesses", [])
            if w.get("description") and w["description"][0]["value"].startswith("CWE-")
        }
    )
    exploits = [
        ExploitReference(url=ref["url"], source=_domain(ref["url"]))
        for ref in cve.get("references", [])
        if "Exploit" in (ref.get("tags") or [])
    ]
    return CveReference(
        cve_id=cve_id,
        description=description[:500],
        cvss_score=score,
        cvss_severity=severity,
        cvss_vector=vector,
        cwe_ids=cwe_ids,
        published=cve.get("published"),
        nvd_url=f"https://nvd.nist.gov/vuln/detail/{cve_id}",
        exploits=exploits[:5],
    )


class NvdClient:
    def __init__(self, api_key: str | None = None, timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._cache: dict[str, tuple[float, CveMatch]] = {}

    async def search_by_keyword(self, term: str, *, move: int | None = None) -> CveMatch:
        """Busca CVEs por palavra-chave. Resultados ordenados por CVSS (maior primeiro)."""
        cached = self._cache.get(term)
        if cached and time.monotonic() - cached[0] < _CACHE_TTL_S:
            return cached[1].model_copy(update={"move": move})

        queried_at = datetime.now(timezone.utc).isoformat()
        headers = {"apiKey": self._api_key} if self._api_key else {}
        params = {"keywordSearch": term, "resultsPerPage": 20}
        try:
            async with httpx.AsyncClient(timeout=self._timeout_s, trust_env=False) as client:
                resp = await client.get(NVD_BASE_URL, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:  # noqa: BLE001 - nunca propaga; vira erro estruturado
            logger.warning("Consulta NVD falhou para %r: %s", term, exc)
            match = CveMatch(search_term=term, move=move, queried_at=queried_at, error=type(exc).__name__)
            return match

        cves = [_parse_cve(v) for v in data.get("vulnerabilities", [])]
        cves.sort(key=lambda c: c.cvss_score or 0.0, reverse=True)
        match = CveMatch(search_term=term, move=move, cves=cves[:_MAX_CVES_PER_TERM], queried_at=queried_at)
        self._cache[term] = (time.monotonic(), match)
        return match


def _domain(url: str) -> str | None:
    m = re.match(r"https?://([^/]+)/?", url)
    return m.group(1) if m else None

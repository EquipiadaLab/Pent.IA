"""Extrai termos de busca REAIS dos achados da campanha e correlaciona com a NVD.

So usa evidencia ja registrada (headers ``server``/``x-powered-by``, ja
mascarados pela allowlist de ``app.redact``). Nunca gera termo a partir de
suposicao: se nenhum lance capturou um header de tecnologia, a lista de
resultados vem vazia.
"""

from __future__ import annotations

from app.cve.models import CveMatch
from app.cve.nvd_client import NvdClient, build_search_term
from app.models import Campaign


def _extract_terms(campaign: Campaign) -> list[tuple[int, str]]:
    """[(numero do lance, termo de busca)], um por evidencia com header de tecnologia."""
    terms: list[tuple[int, str]] = []
    seen: set[str] = set()
    for move in campaign.moves:
        for ev in move.evidence:
            headers = ev.response_headers or {}
            term = build_search_term(headers.get("server"), headers.get("x-powered-by"))
            if term and term.lower() not in seen:
                seen.add(term.lower())
                terms.append((move.move, term))
    return terms


async def correlate_campaign(campaign: Campaign, client: NvdClient) -> list[CveMatch]:
    """Consulta a NVD para cada tecnologia observada na campanha. Nunca lanca excecao."""
    terms = _extract_terms(campaign)
    return [await client.search_by_keyword(term, move=move) for move, term in terms]

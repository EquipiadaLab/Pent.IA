"""Testes do DiscoveryAgent (TA0007), sem rede e sem cache ATT&CK real."""

from __future__ import annotations

import pytest

from app.agents.Discovery.catalog import DISCOVERY_TECHNIQUES
from app.agents.Discovery.discovery_agent import DiscoveryAgent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.schemas.agents_contract import AttackReference, TacticDecisionContext


def _context(**overrides) -> TacticDecisionContext:
    data = {
        "campaign_id": "campaign-discovery",
        "available_test_ids": ["INFO-001"],
        "executed_test_ids": [],
        "denied_test_ids": [],
        "remaining_requests": 1,
        "observed_facts": {"origin_scheme": "https"},
    }
    data.update(overrides)
    return TacticDecisionContext(**data)


def _reference() -> AttackReference:
    return AttackReference(
        tactic_id="TA0007",
        tactic_name="Discovery",
        technique_id="T1518",
        technique_name="Software Discovery",
        url="https://attack.mitre.org/techniques/T1518/",
    )


def test_recomenda_apenas_info_001_e_sem_rede(monkeypatch) -> None:
    agent = DiscoveryAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    recommendations = agent.recommend(_context())

    assert len(recommendations) == 1
    item = recommendations[0]
    assert item.agent == "Discovery"
    assert item.test_id == "INFO-001"
    assert item.attack.technique_id == "T1518"
    assert item.request_cost == 1
    assert item.risk == "low"


def test_ignora_ids_fora_do_catalogo_do_motor(monkeypatch) -> None:
    agent = DiscoveryAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(available_test_ids=["FILE-001", "TLS-001"])) == []


@pytest.mark.parametrize("field", ["executed_test_ids", "denied_test_ids"])
def test_nao_recomenda_check_ja_resolvido_ou_negado(monkeypatch, field: str) -> None:
    agent = DiscoveryAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(**{field: ["INFO-001"]})) == []


def test_respeita_orcamento_informado_por_pent(monkeypatch) -> None:
    agent = DiscoveryAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(remaining_requests=0)) == []
    assert agent.recommend(_context(remaining_requests=1))[0].test_id == "INFO-001"


def test_catalogo_mitre_ausente_nao_cria_referencia_falsa(monkeypatch) -> None:
    agent = DiscoveryAgent()

    def unavailable(_: str) -> AttackReference:
        raise AttackCatalogUnavailable("cache ausente")

    monkeypatch.setattr(agent, "attack_reference", unavailable)

    assert agent.recommend(_context()) == []


def test_catalogo_tem_apenas_check_existente_e_limitado() -> None:
    assert [(item.test_id, item.technique_id) for item in DISCOVERY_TECHNIQUES] == [
        ("INFO-001", "T1518")
    ]

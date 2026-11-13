"""Testes do InitialAccessAgent (TA0001), sem rede nem cache ATT&CK real."""

from __future__ import annotations

import pytest

from app.agents.InitialAccess.catalog import INITIAL_ACCESS_TECHNIQUES
from app.agents.InitialAccess.initial_access_agent import InitialAccessAgent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.schemas.agents_contract import AttackReference, TacticDecisionContext


def _context(**overrides) -> TacticDecisionContext:
    data = {
        "campaign_id": "campaign-initial-access",
        "available_test_ids": ["FILE-002"],
        "executed_test_ids": [],
        "denied_test_ids": [],
        "remaining_requests": 1,
    }
    data.update(overrides)
    return TacticDecisionContext(**data)


def _reference() -> AttackReference:
    return AttackReference(
        tactic_id="TA0001",
        tactic_name="Initial Access",
        technique_id="T1078",
        technique_name="Valid Accounts",
        url="https://attack.mitre.org/techniques/T1078/",
    )


def test_recomenda_apenas_file_002_com_linguagem_de_precondicao(monkeypatch) -> None:
    agent = InitialAccessAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    recommendations = agent.recommend(_context())

    assert len(recommendations) == 1
    item = recommendations[0]
    assert item.agent == "InitialAccess"
    assert item.test_id == "FILE-002"
    assert item.attack.tactic_id == "TA0001"
    assert item.attack.technique_id == "T1078"
    assert item.request_cost == 1
    assert "possivel" in item.rationale
    assert "nao tenta login" in item.rationale


def test_nao_recomenda_id_que_pent_nao_liberou(monkeypatch) -> None:
    agent = InitialAccessAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(available_test_ids=["INFO-001"])) == []


@pytest.mark.parametrize("field", ["executed_test_ids", "denied_test_ids"])
def test_nao_recomenda_check_ja_resolvido(monkeypatch, field: str) -> None:
    agent = InitialAccessAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(**{field: ["FILE-002"]})) == []


def test_respeita_orcamento_de_requisicao(monkeypatch) -> None:
    agent = InitialAccessAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(remaining_requests=0)) == []


def test_cache_mitre_ausente_falha_fechado(monkeypatch) -> None:
    agent = InitialAccessAgent()

    def unavailable(_: str) -> AttackReference:
        raise AttackCatalogUnavailable("cache ausente")

    monkeypatch.setattr(agent, "attack_reference", unavailable)

    assert agent.recommend(_context()) == []


def test_catalogo_inicial_nao_inclui_exploit_publico() -> None:
    assert [(item.test_id, item.technique_id) for item in INITIAL_ACCESS_TECHNIQUES] == [
        ("FILE-002", "T1078")
    ]

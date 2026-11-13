"""Testes do CollectionAgent (TA0009), sem rede e sem cache ATT&CK real.

Cobre T1213 (Data from Information Repositories): dados ja acessiveis via
rotas/endpoints que a propria aplicacao publica, sem autenticacao valida.
Outras tecnicas de Collection (ver docstring de
``app.agents.Collection.catalog``) permanecem fora do catalogo porque
exigem um nivel de acesso que o Motor nao possui.
"""

from __future__ import annotations

import pytest

from app.agents.Collection.catalog import COLLECTION_TECHNIQUES
from app.agents.Collection.collection_agent import CollectionAgent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.schemas.agents_contract import AttackReference, TacticDecisionContext

_ALL_TEST_IDS = ("COLLECT-FTP-001", "COLLECT-APIUSERS-001", "COLLECT-APIFEEDBACK-001")


def _context(**overrides) -> TacticDecisionContext:
    data = {
        "campaign_id": "campaign-collection",
        "available_test_ids": list(_ALL_TEST_IDS),
        "executed_test_ids": [],
        "denied_test_ids": [],
        "remaining_requests": 10,
        "observed_facts": {"origin_scheme": "https"},
    }
    data.update(overrides)
    return TacticDecisionContext(**data)


def _reference() -> AttackReference:
    return AttackReference(
        tactic_id="TA0009",
        tactic_name="Collection",
        technique_id="T1213",
        technique_name="Data from Information Repositories",
        url="https://attack.mitre.org/techniques/T1213/",
    )


def test_catalogo_cobre_apenas_t1213() -> None:
    assert {item.technique_id for item in COLLECTION_TECHNIQUES} == {"T1213"}
    assert {item.test_id for item in COLLECTION_TECHNIQUES} == set(_ALL_TEST_IDS)


def test_recomenda_os_tres_checks_disponiveis(monkeypatch) -> None:
    agent = CollectionAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    recommendations = agent.recommend(_context())

    assert {item.test_id for item in recommendations} == set(_ALL_TEST_IDS)
    assert all(item.agent == "Collection" for item in recommendations)
    assert all(item.attack.technique_id == "T1213" for item in recommendations)


def test_ignora_ids_fora_do_catalogo_do_motor(monkeypatch) -> None:
    agent = CollectionAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(available_test_ids=["TLS-001", "FILE-001"])) == []


@pytest.mark.parametrize("field", ["executed_test_ids", "denied_test_ids"])
def test_nao_recomenda_check_ja_resolvido_ou_negado(monkeypatch, field: str) -> None:
    agent = CollectionAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    remaining = agent.recommend(_context(**{field: ["COLLECT-FTP-001"]}))
    assert "COLLECT-FTP-001" not in {item.test_id for item in remaining}


def test_respeita_orcamento_de_requisicao(monkeypatch) -> None:
    agent = CollectionAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(remaining_requests=0)) == []


def test_catalogo_mitre_ausente_nao_cria_referencia_falsa(monkeypatch) -> None:
    agent = CollectionAgent()

    def unavailable(_: str) -> AttackReference:
        raise AttackCatalogUnavailable("cache ausente")

    monkeypatch.setattr(agent, "attack_reference", unavailable)

    assert agent.recommend(_context()) == []


def test_nome_e_tatica_seguem_o_padrao_dos_outros_agentes() -> None:
    agent = CollectionAgent()
    assert agent.name == "Collection"
    assert agent.tactic_id == "TA0009"

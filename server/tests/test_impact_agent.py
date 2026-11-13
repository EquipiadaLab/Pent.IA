"""Testes do ImpactAgent (TA0040) e do check IMPACT-001.

Impact e destrutivo por natureza; o motor so detecta a PRE-CONDICAO de
manipulacao de dados via OPTIONS (nao-mutante). Estes testes garantem que
nenhum metodo destrutivo e enviado.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "devtools"))
import lab_server  # noqa: E402

from app.agents.Impact.catalog import IMPACT_TECHNIQUES
from app.agents.Impact.impact_agent import ImpactAgent
from app.agents.pent import Pent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.engine.checks import CATALOG_BY_ID
from app.engine.memory_sink import MemorySink
from app.engine.runner import run_campaign
from app.engine.scope import utcnow
from app.models import CampaignConfig, CampaignState, Status
from app.schemas.agents_contract import AttackReference, TacticDecisionContext, TechniqueRecommendation


def _context(**overrides) -> TacticDecisionContext:
    data = {
        "campaign_id": "campaign-impact",
        "available_test_ids": ["IMPACT-001"],
        "executed_test_ids": [],
        "denied_test_ids": [],
        "remaining_requests": 5,
    }
    data.update(overrides)
    return TacticDecisionContext(**data)


def _reference() -> AttackReference:
    return AttackReference(
        tactic_id="TA0040",
        tactic_name="Impact",
        technique_id="T1565",
        technique_name="Data Manipulation",
        url="https://attack.mitre.org/techniques/T1565/",
    )


# --- agente (sem rede) -------------------------------------------------------
def test_recomenda_impact_001_mapeado_a_t1565(monkeypatch) -> None:
    agent = ImpactAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    recs = agent.recommend(_context())

    assert len(recs) == 1
    assert recs[0].agent == "Impact"
    assert recs[0].test_id == "IMPACT-001"
    assert recs[0].attack.tactic_id == "TA0040"
    assert recs[0].attack.technique_id == "T1565"


def test_nao_reutiliza_tecnica_de_outro_agente() -> None:
    assert [(t.test_id, t.technique_id) for t in IMPACT_TECHNIQUES] == [("IMPACT-001", "T1565")]


def test_respeita_orcamento_e_cobertura(monkeypatch) -> None:
    agent = ImpactAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(remaining_requests=1)) == []  # custo 2 > 1
    assert agent.recommend(_context(executed_test_ids=["IMPACT-001"])) == []
    assert agent.recommend(_context(denied_test_ids=["IMPACT-001"])) == []
    assert agent.recommend(_context(available_test_ids=["INFO-001"])) == []


def test_falha_fechada_sem_cache_mitre(monkeypatch) -> None:
    agent = ImpactAgent()

    def unavailable(_: str):
        raise AttackCatalogUnavailable("cache ausente")

    monkeypatch.setattr(agent, "attack_reference", unavailable)
    assert agent.recommend(_context()) == []


def test_pent_registra_impact(monkeypatch) -> None:
    rec = _reference()

    def only_impact(self, ctx):
        return [
            TechniqueRecommendation(
                agent="Impact", test_id="IMPACT-001", attack=rec,
                rationale="pre-condicao de manipulacao de dados", priority=60, request_cost=2,
                risk="low", expected_value="medium",
            )
        ]

    monkeypatch.setattr(ImpactAgent, "recommend", only_impact)
    from app.agents.Collection.collection_agent import CollectionAgent
    from app.agents.Discovery.discovery_agent import DiscoveryAgent
    from app.agents.Execution.execution_agent import ExecutionAgent
    from app.agents.InitialAccess.initial_access_agent import InitialAccessAgent
    from app.agents.PrivilegeEscalation.privilege_escalation_agent import PrivilegeEscalationAgent
    from app.agents.Recon.recon_agent import ReconAgent
    for cls in (ReconAgent, DiscoveryAgent, InitialAccessAgent, CollectionAgent,
                PrivilegeEscalationAgent, ExecutionAgent):
        monkeypatch.setattr(cls, "recommend", lambda self, ctx: [])

    decision = Pent().choose_next(_context())
    assert decision.selected is not None
    assert decision.selected.agent == "Impact"
    assert decision.selected.test_id == "IMPACT-001"


# --- check IMPACT-001 end-to-end contra o alvo local -------------------------
@pytest.fixture
def vulnerable():
    srv, url = lab_server.start(hardened=False)
    yield url
    srv.shutdown()


@pytest.fixture
def hardened():
    srv, url = lab_server.start(hardened=True)
    yield url
    srv.shutdown()


def _run(url: str, sink: MemorySink):
    config = CampaignConfig(origin=url, authorized_by="Org", authorized_at=utcnow(),
                            max_requests_per_second=200)
    return asyncio.run(run_campaign("c-impact", config, sink))


def test_impact_001_detecta_superficie_destrutiva_no_vulneravel(vulnerable) -> None:
    assert "IMPACT-001" in CATALOG_BY_ID
    sink = MemorySink(approve=True)
    campaign = _run(vulnerable, sink)
    move = {m.test_id: m for m in campaign.moves}["IMPACT-001"]
    assert campaign.state is CampaignState.FINISHED
    assert move.status is Status.WARNING
    assert move.attack_technique_id == "T1565"
    assert move.recommended_by == "Impact"
    # Garantia central: nenhum metodo destrutivo foi enviado.
    assert all(a.method not in {"PUT", "DELETE", "PATCH"} for a in sink.audits)


def test_impact_001_pass_no_alvo_corrigido(hardened) -> None:
    move = {m.test_id: m for m in _run(hardened, MemorySink(approve=True)).moves}["IMPACT-001"]
    assert move.status is Status.PASS


def test_impact_001_negado_nao_faz_requisicao(vulnerable) -> None:
    sink = MemorySink(approve=False)
    _run(vulnerable, sink)
    assert not any(a.method == "OPTIONS" and a.url.endswith("/api/Products") for a in sink.audits)

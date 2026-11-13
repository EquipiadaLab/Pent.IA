"""Testes do PrivilegeEscalationAgent (TA0004) e do check AUTHZ-001."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "devtools"))
import lab_server  # noqa: E402

from app.agents.PrivilegeEscalation.catalog import PRIVESC_TECHNIQUES
from app.agents.PrivilegeEscalation.privilege_escalation_agent import PrivilegeEscalationAgent
from app.agents.pent import Pent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.engine.checks import CATALOG_BY_ID
from app.engine.memory_sink import MemorySink
from app.engine.runner import run_campaign
from app.engine.scope import utcnow
from app.models import Approval, CampaignConfig, CampaignState, Grade, Status
from app.schemas.agents_contract import AttackReference, TacticDecisionContext


def _context(**overrides) -> TacticDecisionContext:
    data = {
        "campaign_id": "campaign-privesc",
        "available_test_ids": ["AUTHZ-001"],
        "executed_test_ids": [],
        "denied_test_ids": [],
        "remaining_requests": 5,
    }
    data.update(overrides)
    return TacticDecisionContext(**data)


def _reference() -> AttackReference:
    return AttackReference(
        tactic_id="TA0004",
        tactic_name="Privilege Escalation",
        technique_id="T1068",
        technique_name="Exploitation for Privilege Escalation",
        url="https://attack.mitre.org/techniques/T1068/",
    )


# --- agente (sem rede) -------------------------------------------------------
def test_recomenda_authz_001_mapeado_a_t1068(monkeypatch) -> None:
    agent = PrivilegeEscalationAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    recs = agent.recommend(_context())

    assert len(recs) == 1
    assert recs[0].agent == "PrivilegeEscalation"
    assert recs[0].test_id == "AUTHZ-001"
    assert recs[0].attack.tactic_id == "TA0004"
    assert recs[0].attack.technique_id == "T1068"


def test_nao_reutiliza_t1078_para_inflar_cobertura() -> None:
    assert [(t.test_id, t.technique_id) for t in PRIVESC_TECHNIQUES] == [("AUTHZ-001", "T1068")]
    assert all(t.technique_id != "T1078" for t in PRIVESC_TECHNIQUES)


def test_respeita_orcamento_e_cobertura(monkeypatch) -> None:
    agent = PrivilegeEscalationAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(remaining_requests=2)) == []  # custo 3 > 2
    assert agent.recommend(_context(executed_test_ids=["AUTHZ-001"])) == []
    assert agent.recommend(_context(denied_test_ids=["AUTHZ-001"])) == []
    assert agent.recommend(_context(available_test_ids=["INFO-001"])) == []


def test_falha_fechada_sem_cache_mitre(monkeypatch) -> None:
    agent = PrivilegeEscalationAgent()

    def unavailable(_: str):
        raise AttackCatalogUnavailable("cache ausente")

    monkeypatch.setattr(agent, "attack_reference", unavailable)
    assert agent.recommend(_context()) == []


def test_pent_registra_privilege_escalation(monkeypatch) -> None:
    rec = _reference()
    from app.schemas.agents_contract import TechniqueRecommendation

    def only_privesc(self, ctx):
        return [
            TechniqueRecommendation(
                agent="PrivilegeEscalation", test_id="AUTHZ-001", attack=rec,
                rationale="quebra de controle de acesso", priority=70, request_cost=3,
                risk="low", expected_value="high",
            )
        ]

    monkeypatch.setattr(PrivilegeEscalationAgent, "recommend", only_privesc)
    # neutraliza os demais agentes registrados por padrao
    from app.agents.Collection.collection_agent import CollectionAgent
    from app.agents.Discovery.discovery_agent import DiscoveryAgent
    from app.agents.InitialAccess.initial_access_agent import InitialAccessAgent
    from app.agents.Recon.recon_agent import ReconAgent
    for cls in (ReconAgent, DiscoveryAgent, InitialAccessAgent, CollectionAgent):
        monkeypatch.setattr(cls, "recommend", lambda self, ctx: [])

    decision = Pent().choose_next(_context())
    assert decision.selected is not None
    assert decision.selected.agent == "PrivilegeEscalation"
    assert decision.selected.test_id == "AUTHZ-001"


# --- check AUTHZ-001 end-to-end contra o alvo local --------------------------
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
    return asyncio.run(run_campaign("c-authz", config, sink))


def test_authz_001_detecta_acesso_anonimo_no_vulneravel(vulnerable) -> None:
    assert "AUTHZ-001" in CATALOG_BY_ID
    sink = MemorySink(approve=True)
    campaign = _run(vulnerable, sink)
    move = {m.test_id: m for m in campaign.moves}["AUTHZ-001"]
    assert campaign.state is CampaignState.FINISHED
    assert move.status is Status.FAIL
    assert move.grade is Grade.BLUNDER
    assert move.attack_technique_id == "T1068"
    assert move.recommended_by == "PrivilegeEscalation"


def test_authz_001_pass_no_alvo_corrigido(hardened) -> None:
    move = {m.test_id: m for m in _run(hardened, MemorySink(approve=True)).moves}["AUTHZ-001"]
    assert move.status is Status.PASS


def test_authz_001_negado_nao_faz_requisicao(vulnerable) -> None:
    sink = MemorySink(approve=False)
    _run(vulnerable, sink)
    assert not any(a.url.endswith("/api/Users") for a in sink.audits)

"""Integração determinística de Initial Access no coordenador Pent."""

from __future__ import annotations

from app.agents.Collection.collection_agent import CollectionAgent
from app.agents.Discovery.discovery_agent import DiscoveryAgent
from app.agents.InitialAccess.initial_access_agent import InitialAccessAgent
from app.agents.Recon.recon_agent import ReconAgent
from app.agents.pent import Pent
from app.schemas.agents_contract import AttackReference, TacticDecisionContext, TechniqueRecommendation


def _recommendation() -> TechniqueRecommendation:
    return TechniqueRecommendation(
        agent="InitialAccess",
        test_id="FILE-002",
        attack=AttackReference(
            tactic_id="TA0001",
            tactic_name="Initial Access",
            technique_id="T1078",
            technique_name="Valid Accounts",
        ),
        rationale="Exposicao potencial de material para contas validas.",
        priority=85,
        request_cost=1,
        risk="low",
        expected_value="high",
    )


def test_pent_registra_initial_access_e_preserva_validacao(monkeypatch) -> None:
    # Isola o registro do Pent do cache ATT&CK; cada agente continua sendo
    # avaliado pelo proprio Pent contra available_test_ids e CATALOG_BY_ID.
    monkeypatch.setattr(ReconAgent, "recommend", lambda self, ctx: [])
    monkeypatch.setattr(DiscoveryAgent, "recommend", lambda self, ctx: [])
    monkeypatch.setattr(InitialAccessAgent, "recommend", lambda self, ctx: [_recommendation()])
    monkeypatch.setattr(CollectionAgent, "recommend", lambda self, ctx: [])

    decision = Pent().choose_next(
        TacticDecisionContext(
            campaign_id="campaign-1",
            available_test_ids=["FILE-002"],
            remaining_requests=1,
        )
    )

    assert decision.selected is not None
    assert decision.selected.agent == "InitialAccess"
    assert decision.selected.test_id == "FILE-002"
    assert decision.selected.attack.tactic_id == "TA0001"
    assert decision.selected.attack.technique_id == "T1078"


def test_pent_descarta_recomendacao_initial_access_fora_da_lista(monkeypatch) -> None:
    monkeypatch.setattr(ReconAgent, "recommend", lambda self, ctx: [])
    monkeypatch.setattr(DiscoveryAgent, "recommend", lambda self, ctx: [])
    monkeypatch.setattr(InitialAccessAgent, "recommend", lambda self, ctx: [_recommendation()])
    monkeypatch.setattr(CollectionAgent, "recommend", lambda self, ctx: [])

    decision = Pent().choose_next(
        TacticDecisionContext(
            campaign_id="campaign-1",
            available_test_ids=["INFO-001"],
            remaining_requests=1,
        )
    )

    assert decision.selected is None

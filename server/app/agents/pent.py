"""Pent, o agente master do PENT.IA.

Pent coordena agentes especialistas. Ele nao executa HTTP, nao cria comandos e
nao concede permissao a si proprio. Sua saida e uma recomendacao de um
``test_id`` do catalogo fechado; o runner continua responsavel por:

1. validar escopo e limites;
2. criar um Move pendente;
3. aguardar aprovacao humana;
4. executar o CheckSpec apenas depois da aprovacao.
"""

from __future__ import annotations

from app.agents.Collection.collection_agent import CollectionAgent
from app.agents.CredentialAccess.credential_access_agent import CredentialAccessAgent
from app.agents.Discovery.discovery_agent import DiscoveryAgent
from app.agents.Execution.execution_agent import ExecutionAgent
from app.agents.Impact.impact_agent import ImpactAgent
from app.agents.InitialAccess.initial_access_agent import InitialAccessAgent
from app.agents.PrivilegeEscalation.privilege_escalation_agent import PrivilegeEscalationAgent
from app.agents.Recon.recon_agent import ReconAgent
from app.agents.base_agent import BaseTacticAgent
from app.engine.checks import CATALOG_BY_ID
from app.schemas.agents_contract import PentDecision, TacticDecisionContext, TechniqueRecommendation

_PHASE_ORDER = {"opening": 0, "middlegame": 1, "endgame": 2}


class Pent:
    """Coordenador deterministico dos agentes especialistas disponiveis."""

    name = "Pent"

    def __init__(self, agents: list[BaseTacticAgent] | None = None) -> None:
        # Registro explicito e deterministico: cada agente so recomenda
        # checks existentes; Pent continua sendo o arbitro comum.
        self._agents = (
            agents
            if agents is not None
            else [
                ReconAgent(),
                DiscoveryAgent(),
                InitialAccessAgent(),
                CollectionAgent(),
                PrivilegeEscalationAgent(),
                ExecutionAgent(),
                ImpactAgent(),
                CredentialAccessAgent(),
            ]
        )

    def choose_next(self, context: TacticDecisionContext) -> PentDecision:
        """Seleciona a melhor sugestao valida, sem rede e sem efeitos.

        Defesa em profundidade: mesmo que um agente tenha bug ou uma futura IA
        sugira um id inventado, Pent descarta a sugestao se ela nao estiver no
        catalogo fechado ou se nao fizer parte dos ids pre-filtrados pelo
        runner.
        """
        allowed = set(context.available_test_ids)
        available_specs = {
            test_id: CATALOG_BY_ID[test_id]
            for test_id in allowed
            if test_id in CATALOG_BY_ID
        }
        if not available_specs:
            return PentDecision(
                campaign_id=context.campaign_id,
                reason="Nao ha mais testes implementados, permitidos e aplicaveis para esta campanha.",
            )

        # O master respeita a progressao da campanha. Um agente de endgame
        # nao pode pular abertura/meio-jogo apenas por ter prioridade alta.
        current_phase_order = min(
            _PHASE_ORDER[spec.phase.value] for spec in available_specs.values()
        )
        candidates: list[TechniqueRecommendation] = []

        for agent in self._agents:
            for recommendation in agent.recommend(context):
                spec = available_specs.get(recommendation.test_id)
                if spec is None:
                    continue
                if _PHASE_ORDER[spec.phase.value] != current_phase_order:
                    continue
                candidates.append(recommendation)

        if not candidates:
            return PentDecision(
                campaign_id=context.campaign_id,
                reason="Nao ha mais testes implementados, permitidos e aplicaveis para esta campanha.",
            )

        # Maior utilidade primeiro. Em empate, prioriza menor custo de
        # requisicoes e, por fim, o identificador estavel para ser auditavel.
        ordered = sorted(
            candidates,
            key=lambda item: (-item.priority, item.request_cost, item.test_id),
        )
        selected = ordered[0]
        return PentDecision(
            campaign_id=context.campaign_id,
            selected=selected,
            considered=ordered,
            reason=(
                f"{selected.agent} recomendou {selected.test_id} como proximo lance: "
                f"{selected.rationale}"
            ),
        )

"""Pent, o agente master do Pentest Chess.

Pent coordena agentes especialistas. Ele nao executa HTTP, nao cria comandos e
nao concede permissao a si proprio. Sua saida e uma recomendacao de um
``test_id`` do catalogo fechado; o runner continua responsavel por:

1. validar escopo e limites;
2. criar um Move pendente;
3. aguardar aprovacao humana;
4. executar o CheckSpec apenas depois da aprovacao.
"""

from __future__ import annotations

from app.agents.Discovery.discovery_agent import DiscoveryAgent
from app.agents.Recon.recon_agent import ReconAgent
from app.agents.base_agent import BaseTacticAgent
from app.engine.checks import CATALOG_BY_ID
from app.schemas.agents_contract import PentDecision, TacticDecisionContext, TechniqueRecommendation


def default_agents() -> list[BaseTacticAgent]:
    """Agentes de tatica ja implementados. Cada novo agente entra aqui com
    uma linha; a regra de seguranca do Pent nao muda."""
    return [ReconAgent(), DiscoveryAgent()]


class Pent:
    """Coordenador deterministico dos agentes especialistas disponiveis."""

    name = "Pent"

    def __init__(self, agents: list[BaseTacticAgent] | None = None) -> None:
        self._agents = agents if agents is not None else default_agents()

    def choose_next(self, context: TacticDecisionContext) -> PentDecision:
        """Seleciona a melhor sugestao valida, sem rede e sem efeitos.

        Defesa em profundidade: mesmo que um agente tenha bug ou uma futura IA
        sugira um id inventado, Pent descarta a sugestao se ela nao estiver no
        catalogo fechado ou se nao fizer parte dos ids pre-filtrados pelo
        runner.
        """
        allowed = set(context.available_test_ids)
        candidates: list[TechniqueRecommendation] = []

        for agent in self._agents:
            for recommendation in agent.recommend(context):
                if recommendation.test_id not in allowed:
                    continue
                if recommendation.test_id not in CATALOG_BY_ID:
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

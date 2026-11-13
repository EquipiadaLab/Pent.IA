"""Agente especialista da tatica MITRE TA0043: Reconnaissance.

O Recon NAO executa requisicoes. Ele recebe de Pent uma fotografia segura da
campanha e recomenda testes do seu catalogo fechado. Pent continua responsavel
por validar a recomendacao, criar o lance, pedir aprovacao humana e mandar o
Motor executar o CheckSpec ja existente.
"""

from __future__ import annotations

from app.agents.Recon.catalog import RECON_TECHNIQUES
from app.agents.base_agent import BaseTacticAgent
from app.schemas.agents_contract import TacticDecisionContext, TechniqueRecommendation


class ReconAgent(BaseTacticAgent):
    tactic_id = "TA0043"
    name = "Recon"

    def recommend(self, context: TacticDecisionContext) -> list[TechniqueRecommendation]:
        """Devolve opcoes de Recon ordenadas, sem rede e sem efeitos colaterais.

        Pent ja entrega apenas ids elegiveis. O agente repete os filtros de
        executado/negado como defesa em profundidade e descarta uma opcao cujo
        custo nao caiba no orcamento restante.
        """
        available = set(context.available_test_ids)
        executed = set(context.executed_test_ids)
        denied = set(context.denied_test_ids)
        recommendations: list[TechniqueRecommendation] = []

        for candidate in RECON_TECHNIQUES:
            if candidate.test_id not in available:
                continue
            if candidate.test_id in executed or candidate.test_id in denied:
                continue
            if candidate.request_cost > context.remaining_requests:
                continue
            if not candidate.applies(context):
                continue

            recommendations.append(
                TechniqueRecommendation(
                    agent=self.name,
                    test_id=candidate.test_id,
                    attack=self.attack_reference(candidate.technique_id),
                    rationale=candidate.rationale,
                    priority=candidate.base_priority,
                    request_cost=candidate.request_cost,
                    risk=candidate.risk,
                    expected_value=candidate.expected_value,
                )
            )

        return sorted(recommendations, key=lambda item: item.priority, reverse=True)

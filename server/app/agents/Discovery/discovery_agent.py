"""Agente especialista da tatica MITRE ATT&CK TA0007: Discovery.

O agente nao acessa rede e nao executa checks. Ele recebe de Pent uma
fotografia segura da campanha e recomenda somente ``test_id``s que pertencem
ao catalogo fechado do Motor. Pent valida a recomendacao; o runner mantem
escopo, aprovacao, auditoria, stop e execucao pelo Fetcher.

No MVP, a cobertura e T1518 (Software Discovery) no limite do produto web:
identificadores de software expostos pela propria aplicacao HTTP. Isso nao
cobre descoberta de host, processos, rede, portas ou arquivos.
"""

from __future__ import annotations

from app.agents.Discovery.catalog import DISCOVERY_TECHNIQUES
from app.agents.base_agent import BaseTacticAgent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.schemas.agents_contract import TacticDecisionContext, TechniqueRecommendation


class DiscoveryAgent(BaseTacticAgent):
    """Recomenda checks seguros e elegiveis para a tatica Discovery."""

    tactic_id = "TA0007"
    name = "Discovery"

    def recommend(self, context: TacticDecisionContext) -> list[TechniqueRecommendation]:
        """Devolve sugestoes ordenadas, sem rede e sem efeitos colaterais.

        Pent fornece a intersecao de checks elegiveis. O agente repete os
        filtros de cobertura, negacao e orcamento como defesa em profundidade.
        Sem o catalogo ATT&CK local, nao fabrica referencias: retorna lista
        vazia para que Pent encerre ou siga com outro agente de forma segura.
        """
        available = set(context.available_test_ids)
        executed = set(context.executed_test_ids)
        denied = set(context.denied_test_ids)
        recommendations: list[TechniqueRecommendation] = []

        try:
            for candidate in DISCOVERY_TECHNIQUES:
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
        except (AttackCatalogUnavailable, KeyError, OSError, ValueError):
            return []

        return sorted(recommendations, key=lambda item: item.priority, reverse=True)

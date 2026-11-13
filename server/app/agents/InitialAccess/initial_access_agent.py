"""Agente especialista da tatica MITRE ATT&CK TA0001: Initial Access.

O Initial Access nao acessa rede e nao executa tecnicas. Ele recomenda apenas
checks existentes do catalogo fechado; Pent, o runner e o Motor mantem a
validacao de escopo, aprovacao humana obrigatoria e execucao segura.
"""

from __future__ import annotations

from app.agents.InitialAccess.catalog import INITIAL_ACCESS_TECHNIQUES
from app.agents.base_agent import BaseTacticAgent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.schemas.agents_contract import TacticDecisionContext, TechniqueRecommendation


class InitialAccessAgent(BaseTacticAgent):
    """Recomenda verificacao controlada de possivel caminho de acesso inicial."""

    tactic_id = "TA0001"
    name = "InitialAccess"

    def recommend(self, context: TacticDecisionContext) -> list[TechniqueRecommendation]:
        """Devolve sugestoes sem efeitos e sem fabricar referencias ATT&CK."""
        available = set(context.available_test_ids)
        executed = set(context.executed_test_ids)
        denied = set(context.denied_test_ids)
        recommendations: list[TechniqueRecommendation] = []

        try:
            for candidate in INITIAL_ACCESS_TECHNIQUES:
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

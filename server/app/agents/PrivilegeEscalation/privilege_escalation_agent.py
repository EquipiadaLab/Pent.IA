"""Agente especialista da tatica MITRE ATT&CK TA0004: Privilege Escalation.

Nao acessa rede e nao executa checks. Recomenda apenas IDs do catalogo fechado;
Pent, o runner e o Motor mantem validacao de escopo, aprovacao humana
obrigatoria e execucao segura pelo Fetcher.
"""

from __future__ import annotations

from app.agents.PrivilegeEscalation.catalog import PRIVESC_TECHNIQUES
from app.agents.base_agent import BaseTacticAgent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.schemas.agents_contract import TacticDecisionContext, TechniqueRecommendation


class PrivilegeEscalationAgent(BaseTacticAgent):
    """Recomenda verificacao de quebra de controle de acesso (A01) como TA0004."""

    tactic_id = "TA0004"
    name = "PrivilegeEscalation"

    def recommend(self, context: TacticDecisionContext) -> list[TechniqueRecommendation]:
        """Sugestoes sem efeitos; falha fechada se a referencia ATT&CK faltar."""
        available = set(context.available_test_ids)
        executed = set(context.executed_test_ids)
        denied = set(context.denied_test_ids)
        recommendations: list[TechniqueRecommendation] = []

        try:
            for candidate in PRIVESC_TECHNIQUES:
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

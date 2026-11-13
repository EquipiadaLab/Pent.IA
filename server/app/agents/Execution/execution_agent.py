"""Agente especialista da tatica MITRE ATT&CK TA0002: Execution.

Nao acessa rede e nao executa checks. Recomenda apenas IDs do catalogo
fechado; Pent, o runner e o Motor mantem validacao de escopo, aprovacao
humana obrigatoria e execucao segura pelo Fetcher. A IA NUNCA decide, por
conta propria, executar um teste de Execution: toda recomendacao passa pelo
mesmo portao de aprovacao humana e parada de emergencia dos demais testes
sensiveis do catalogo (ver ``EXECUTION_TECHNIQUES`` e ``needs_approval``
em ``app.engine.checks``).
"""

from __future__ import annotations

from app.agents.Execution.catalog import EXECUTION_TECHNIQUES
from app.agents.base_agent import BaseTacticAgent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.schemas.agents_contract import TacticDecisionContext, TechniqueRecommendation


class ExecutionAgent(BaseTacticAgent):
    """Recomenda prova de conceito nao-destrutiva de SSTI como TA0002."""

    tactic_id = "TA0002"
    name = "Execution"

    def recommend(self, context: TacticDecisionContext) -> list[TechniqueRecommendation]:
        """Sugestoes sem efeitos; falha fechada se a referencia ATT&CK faltar."""
        available = set(context.available_test_ids)
        executed = set(context.executed_test_ids)
        denied = set(context.denied_test_ids)
        recommendations: list[TechniqueRecommendation] = []

        try:
            for candidate in EXECUTION_TECHNIQUES:
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

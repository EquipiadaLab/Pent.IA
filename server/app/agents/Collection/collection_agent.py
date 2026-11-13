"""Agente especialista da tatica MITRE ATT&CK TA0009: Collection.

O agente nao acessa rede e nao executa checks. Ele recebe de Pent uma
fotografia segura da campanha e recomenda somente ``test_id``s que pertencem
ao catalogo fechado do Motor. Pent valida a recomendacao; o runner mantem
escopo, aprovacao, auditoria, stop e execucao pelo Fetcher.

Cobertura atual: T1213 (Data from Information Repositories) via
``COLLECTION_TECHNIQUES`` -- dados ja acessiveis atraves de rotas/endpoints
REST publicados pela propria aplicacao, sem autenticacao valida (ver
``app.agents.Collection.catalog``). Outras tecnicas de Collection (capturas
de tela, keylogging, arquivos locais do sistema operacional, etc.) exigem um
nivel de acesso que este Motor nao possui e por isso nao sao representadas.
"""

from __future__ import annotations

from app.agents.Collection.catalog import COLLECTION_TECHNIQUES
from app.agents.base_agent import BaseTacticAgent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.schemas.agents_contract import TacticDecisionContext, TechniqueRecommendation


class CollectionAgent(BaseTacticAgent):
    """Recomenda checks seguros e elegiveis para a tatica Collection.

    Hoje sempre devolve lista vazia: ver ``app.agents.Collection.catalog``.
    """

    tactic_id = "TA0009"
    name = "Collection"

    def recommend(self, context: TacticDecisionContext) -> list[TechniqueRecommendation]:
        """Devolve sugestoes ordenadas, sem rede e sem efeitos colaterais.

        Pent fornece a intersecao de checks elegiveis. O agente repete os
        filtros de cobertura, negacao e orcamento como defesa em profundidade,
        igual aos demais agentes de tatica. Sem o catalogo ATT&CK local, nao
        fabrica referencias: retorna lista vazia para que Pent siga com outro
        agente de forma segura.
        """
        available = set(context.available_test_ids)
        executed = set(context.executed_test_ids)
        denied = set(context.denied_test_ids)
        recommendations: list[TechniqueRecommendation] = []

        try:
            for candidate in COLLECTION_TECHNIQUES:
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

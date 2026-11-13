"""Classe base para agentes especialistas de taticas MITRE ATT&CK.

Cada agente cobre uma tatica e recomenda testes de um catalogo fechado. Ele
nao faz chamadas HTTP e nao executa tecnicas por conta propria. O agente
master Pent valida a sugestao e o Motor executa somente depois da aprovacao
humana.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.attack_mitre import get_catalog
from app.schemas.agents_contract import AttackReference, TacticDecisionContext, TechniqueRecommendation


class BaseTacticAgent(ABC):
    """Um agente especialista de uma tatica ATT&CK."""

    tactic_id: str
    name: str

    def attack_reference(self, technique_id: str) -> AttackReference:
        """Retorna dados MITRE reais do cache local, nunca nomes inventados."""
        return get_catalog().reference_for(technique_id, tactic_id=self.tactic_id)

    @abstractmethod
    def recommend(self, context: TacticDecisionContext) -> list[TechniqueRecommendation]:
        """Sugere testes elegiveis para a tatica, sem rede e sem efeitos.

        O retorno nunca e uma permissao de execucao. Pent precisa validar a
        recomendacao contra o catalogo, escopo e estado; depois o responsavel
        humano ainda precisa aprovar o lance no front-end.
        """
        raise NotImplementedError

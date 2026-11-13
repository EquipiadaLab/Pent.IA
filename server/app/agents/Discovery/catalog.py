"""Mapa fechado: Discovery (TA0007) -> checks web existentes.

O Discovery nao executa probes. Ele recomenda somente IDs presentes no
catalogo do Motor, e Pent continua responsavel por validar escopo, criar o
lance e aguardar aprovacao antes da execucao.

T1518 (Software Discovery) e aplicado de forma restrita: ``INFO-001``
avalia identificadores de software que a aplicacao ja expoe em cabecalhos
HTTP publicos. Isso NAO e uma alegacao de inventario do sistema hospedeiro,
nem habilita descoberta de processos, arquivos, rede ou portas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.schemas.agents_contract import TacticDecisionContext


@dataclass(frozen=True)
class DiscoveryTechnique:
    test_id: str
    technique_id: str
    base_priority: int
    request_cost: int
    risk: str
    expected_value: str
    rationale: str
    applies: Callable[[TacticDecisionContext], bool]


def _always(_: TacticDecisionContext) -> bool:
    return True


# A lista e deliberadamente pequena. Novos itens so entram quando houver um
# CheckSpec correspondente e uma justificativa ATT&CK tecnicamente correta.
DISCOVERY_TECHNIQUES: tuple[DiscoveryTechnique, ...] = (
    DiscoveryTechnique(
        test_id="INFO-001",
        technique_id="T1518",
        base_priority=90,
        # A observacao-base so ocorre depois da aprovacao humana do lance;
        # por isso este check pode consumir uma requisicao GET segura.
        request_cost=1,
        risk="low",
        expected_value="medium",
        rationale=(
            "Avaliar identificadores de software publicados em cabecalhos HTTP, "
            "em uma requisicao GET previamente aprovada, sem inferir inventario do host."
        ),
        applies=_always,
    ),
)

"""Mapa fechado: Impact (TA0040) -> checks web existentes.

Mapeamento tecnico: as tecnicas de Impact sao destrutivas (destruicao,
criptografia, DoS, defacement) e o Pent.IA nao executa nenhuma delas. A
manifestacao SEGURA e defensavel em um motor black-box e detectar a
PRE-CONDICAO de manipulacao de dados: endpoints de dados que anunciam metodos
destrutivos a um cliente anonimo.

``IMPACT-001`` -> T1565 (Data Manipulation). O check so usa OPTIONS (nao
altera estado). Nao reutilizamos tecnicas ja mapeadas por outros agentes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.schemas.agents_contract import TacticDecisionContext


@dataclass(frozen=True)
class ImpactTechnique:
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


IMPACT_TECHNIQUES: tuple[ImpactTechnique, ...] = (
    ImpactTechnique(
        test_id="IMPACT-001",
        technique_id="T1565",
        base_priority=60,
        # Dois OPTIONS, nao-mutantes.
        request_cost=2,
        risk="low",
        expected_value="medium",
        rationale=(
            "Medir, apos aprovacao humana, se endpoints de dados anunciam metodos "
            "destrutivos (PUT/DELETE/PATCH) via OPTIONS. E uma pre-condicao para "
            "manipulacao de dados; o teste nao envia metodos destrutivos nem altera nada."
        ),
        applies=_always,
    ),
)

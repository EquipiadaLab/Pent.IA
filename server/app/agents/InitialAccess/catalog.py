"""Mapa fechado: Initial Access (TA0001) -> checks web existentes.

O agente recomenda apenas checks que o Motor ja suporta. O MVP limita-se a
``FILE-002`` como evidencia de *possivel* exposicao de material que poderia
viabilizar T1078 (Valid Accounts). O check nao le nem persiste valores de
segredos, nao tenta autenticar e nao comprova uma conta valida.

T1190 (Exploit Public-Facing Application) fica fora: o Motor nao executa
payloads, fuzzing ou exploracao, e nenhum CheckSpec existente o demonstra de
modo tecnicamente justificavel.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.schemas.agents_contract import TacticDecisionContext


@dataclass(frozen=True)
class InitialAccessTechnique:
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


INITIAL_ACCESS_TECHNIQUES: tuple[InitialAccessTechnique, ...] = (
    InitialAccessTechnique(
        test_id="FILE-002",
        technique_id="T1078",
        base_priority=85,
        request_cost=1,
        risk="low",
        expected_value="high",
        rationale=(
            "Verificar, somente apos aprovacao humana, se /.env esta exposto. "
            "Uma exposicao e uma possivel pre-condicao para material que viabilize abuso de contas validas; "
            "o teste nao le valores, nao tenta login e nao confirma credenciais."
        ),
        applies=_always,
    ),
)

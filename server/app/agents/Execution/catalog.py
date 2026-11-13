"""Mapa fechado: Execution (TA0002) -> checks web existentes.

Execution descreve fazer codigo do atacante rodar no sistema do alvo (RCE).
Um avaliador HTTP black-box nao deve executar exploracao destrutiva real:
o check ``EXEC-SSTI-001`` e uma prova de conceito NAO-DESTRUTIVA que envia
expressoes aritmeticas inofensivas e verifica se o servidor as avaliou,
provando a condicao (motor de template interpretando entrada do usuario
como codigo) sem rodar comando de sistema, upload de shell ou qualquer
acao que possa corromper ou indisponibilizar o alvo.

Mapeado a T1190 (Exploit Public-Facing Application) como APROXIMACAO
consciente: o check detecta a condicao necessaria para exploracao, nao
realiza a exploracao completa (RCE de fato).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.schemas.agents_contract import TacticDecisionContext


@dataclass(frozen=True)
class ExecutionTechnique:
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


EXECUTION_TECHNIQUES: tuple[ExecutionTechnique, ...] = (
    ExecutionTechnique(
        test_id="EXEC-SSTI-001",
        technique_id="T1190",
        base_priority=65,
        # 3 sondagens aritmeticas inofensivas (uma por sintaxe de template comum).
        request_cost=3,
        risk="medium",
        expected_value="high",
        rationale=(
            "Verificar, apos aprovacao humana, se o endpoint de busca avalia expressoes "
            "aritmeticas inofensivas enviadas no parametro de consulta (prova de conceito "
            "de Server-Side Template Injection). O teste nao executa comando de sistema, "
            "nao sobe shell e nao altera ou apaga dados."
        ),
        applies=_always,
    ),
)

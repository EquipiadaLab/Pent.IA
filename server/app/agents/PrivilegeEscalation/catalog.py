"""Mapa fechado: Privilege Escalation (TA0004) -> checks web existentes.

Mapeamento tecnico: um avaliador HTTP black-box nao executa exploits de SO,
tokens ou processos. A manifestacao web defensavel de "obter nivel de acesso
mais alto" e a QUEBRA DE CONTROLE DE ACESSO (OWASP A01): um cliente anonimo
alcanca dados/funcao que deveriam exigir privilegio.

Associamos ``AUTHZ-001`` a T1068 (Exploitation for Privilege Escalation) como
APROXIMACAO consciente: o check detecta a CONDICAO (recurso privilegiado
alcancavel sem autorizacao), nao realiza a exploracao. Nao reutilizamos T1078,
ja usado por Initial Access, para nao inflar cobertura.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.schemas.agents_contract import TacticDecisionContext


@dataclass(frozen=True)
class PrivEscTechnique:
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


PRIVESC_TECHNIQUES: tuple[PrivEscTechnique, ...] = (
    PrivEscTechnique(
        test_id="AUTHZ-001",
        technique_id="T1068",
        base_priority=70,
        # Consulta uma lista fixa e curta de endpoints privilegiados por GET.
        request_cost=3,
        risk="low",
        expected_value="high",
        rationale=(
            "Verificar, apos aprovacao humana, se endpoints privilegiados conhecidos "
            "respondem a um cliente anonimo (quebra de controle de acesso). O teste nao "
            "explora, nao autentica e nao le valores de segredo."
        ),
        applies=_always,
    ),
)

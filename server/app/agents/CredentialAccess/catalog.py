"""Mapa fechado: Credential Access (TA0006) -> checks web existentes.

T1212 (Exploitation for Credential Access): uma falha de injecao no fluxo de
autenticacao permite obter um token de sessao sem credenciais validas.
``CREDS-SQLI-LOGIN-001`` e o unico check mapeado aqui; ele confirma o
bypass com um unico POST (payload classico de SQL Injection no campo de
email) e nao reutiliza o token obtido para nenhuma acao adicional.

T1110 (Brute Force) e T1552 (Unsecured Credentials in Files) ficam de fora:
o Motor nao faz forca bruta de senha real, e exposicao de segredos em
arquivos ja e coberta por Initial Access (``FILE-002``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.schemas.agents_contract import TacticDecisionContext


@dataclass(frozen=True)
class CredentialAccessTechnique:
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


CREDENTIAL_ACCESS_TECHNIQUES: tuple[CredentialAccessTechnique, ...] = (
    CredentialAccessTechnique(
        test_id="CREDS-SQLI-LOGIN-001",
        technique_id="T1212",
        base_priority=80,
        request_cost=1,
        risk="medium",
        expected_value="high",
        rationale=(
            "Verificar, apos aprovacao humana, se o endpoint de login autentica um payload "
            "classico de SQL Injection sem exigir credenciais reais. O teste nao reutiliza o "
            "token obtido e nao tenta payloads destrutivos."
        ),
        applies=_always,
    ),
)

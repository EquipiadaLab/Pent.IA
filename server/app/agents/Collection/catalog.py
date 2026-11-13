"""Mapa fechado: Collection (TA0009) -> checks web existentes.

A maior parte das tecnicas de Collection descreve coleta de dados APOS algum
nivel de acesso ao sistema do alvo: capturas de tela (T1113), keylogging
(T1056.001), leitura de arquivos locais (T1005), area de transferencia
(T1115), e-mail local (T1114.001), audio/video (T1123/T1125). O Motor deste
produto nao tem esse nivel de acesso e nao representa essas tecnicas.

T1213 (Data from Information Repositories) e diferente: cobre dados de
interesse ja acessiveis atraves de repositorios/rotas que a propria
aplicacao publica, sem exigir autenticacao valida. Para um alvo de treino
como o OWASP Juice Shop, isso corresponde a rotas e endpoints REST
conhecidos que costumam vazar dados sem controle de acesso adequado
(``COLLECT-FTP-001``, ``COLLECT-APIUSERS-001``, ``COLLECT-APIFEEDBACK-001``).
Cada check faz apenas GET de leitura; nenhum tenta login, injecao ou forja
de token.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.schemas.agents_contract import TacticDecisionContext


@dataclass(frozen=True)
class CollectionTechnique:
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


COLLECTION_TECHNIQUES: tuple[CollectionTechnique, ...] = (
    CollectionTechnique(
        test_id="COLLECT-FTP-001",
        technique_id="T1213",
        base_priority=70,
        request_cost=1,
        risk="low",
        expected_value="high",
        rationale="Verificar se /ftp expoe listagem de arquivos sem exigir autenticacao.",
        applies=_always,
    ),
    CollectionTechnique(
        test_id="COLLECT-APIUSERS-001",
        technique_id="T1213",
        base_priority=75,
        request_cost=1,
        risk="low",
        expected_value="high",
        rationale="Verificar se a API de usuarios responde registros sem exigir uma sessao autenticada.",
        applies=_always,
    ),
    CollectionTechnique(
        test_id="COLLECT-APIFEEDBACK-001",
        technique_id="T1213",
        base_priority=60,
        request_cost=1,
        risk="low",
        expected_value="medium",
        rationale="Verificar se a API de feedback associa comentarios a identificadores de usuario sem autenticacao.",
        applies=_always,
    ),
)

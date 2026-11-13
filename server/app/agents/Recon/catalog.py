"""Mapa fechado: Reconnaissance -> testes web que o Pentest Chess suporta.

MITRE ATT&CK e um catalogo de comportamento adversario; ele nao entrega
comandos prontos de pentest web. Esta tabela e a camada de traducao segura:
o agente Recon so pode recomendar um ``test_id`` que esteja aqui E que ja
exista em ``app.engine.checks.CATALOG``.

T1595 (Active Scanning) e usado como referencia de contexto para estes testes
leves de superficie HTTP/TLS. A execucao continua sendo o CheckSpec interno,
nunca uma instrucao/tecnica MITRE executada diretamente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.schemas.agents_contract import TacticDecisionContext


@dataclass(frozen=True)
class ReconTechnique:
    test_id: str
    technique_id: str
    base_priority: int
    request_cost: int
    risk: str
    expected_value: str
    rationale: str
    applies: Callable[[TacticDecisionContext], bool]


def _is_https(ctx: TacticDecisionContext) -> bool:
    return ctx.observed_facts.get("origin_scheme") == "https"


def _is_http(ctx: TacticDecisionContext) -> bool:
    return ctx.observed_facts.get("origin_scheme") == "http"


def _always(_: TacticDecisionContext) -> bool:
    return True


# Ordem e pontuacao sao explicitas e auditaveis, nao uma decisao escondida
# dentro de um prompt de IA. Uma IA pode, depois, explicar a sugestao do Pent,
# mas nao altera esta lista nem cria novos testes.
RECON_TECHNIQUES: tuple[ReconTechnique, ...] = (
    ReconTechnique(
        test_id="TLS-001",
        technique_id="T1595",
        base_priority=100,
        request_cost=0,  # avalia o esquema da origem; nao precisa nova chamada
        risk="low",
        expected_value="high",
        rationale="Confirmar se a origem autorizada usa HTTPS antes de qualquer analise posterior.",
        applies=_is_http,
    ),
    ReconTechnique(
        test_id="TLS-002",
        technique_id="T1595",
        base_priority=95,
        request_cost=1,
        risk="low",
        expected_value="high",
        rationale="Validar a cadeia do certificado TLS da origem HTTPS antes dos proximos lances.",
        applies=_is_https,
    ),
    ReconTechnique(
        test_id="REDIR-001",
        technique_id="T1595",
        base_priority=90,
        request_cost=1,
        risk="low",
        expected_value="high",
        rationale="Verificar se visitantes que chegam por HTTP sao protegidos por redirecionamento para HTTPS.",
        applies=_is_https,
    ),
    # O fingerprint de tecnologia e responsabilidade exclusiva do
    # DiscoveryAgent (TA0007/T1518), evitando dois agentes recomendarem o
    # mesmo CheckSpec.
)

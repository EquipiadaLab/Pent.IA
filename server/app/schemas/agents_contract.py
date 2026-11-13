"""Contrato dos agentes de tatica (ex.: Recon) e do agente master (Pent).

Alinhado ao MITRE ATT&CK (https://attack.mitre.org/): cada agente de tatica
cobre UMA tatica ATT&CK (ex. TA0043 Reconnaissance) e, dentro dela, executa
uma ou mais tecnicas/sub-tecnicas (ex. T1595 Active Scanning).

Vocabulario ATT&CK usado aqui:
- ``tactic``    = o "porque" (objetivo do atacante). Ex.: Reconnaissance.
- ``technique`` = o "como" (o que foi efetivamente testado). Ex.: T1595.002.

Este arquivo reaproveita os enums de ``app.models`` (Severity, Status) em vez
de recria-los, para nao divergir do contrato principal usado por Move/Campaign.
Campos novos aqui sao sempre opcionais ou com default, para nao quebrar quem
ja consome ``app.models``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models import Severity, Status


class AgentStatus(str):
    """Mantido como alias de compatibilidade; prefira ``app.models.Status``.

    Os dois valores extra que nao existem em Status (BLOCKED_BY_SCOPE) sao
    representados via o campo ``blocked_reason`` em vez de um enum paralelo.
    """


# --------------------------------------------------------------------------
# MITRE ATT&CK: referencia de tatica/tecnica usada por achado e por agente.
# --------------------------------------------------------------------------
class AttackReference(BaseModel):
    """Aponta um achado ou agente para o catalogo oficial do MITRE ATT&CK."""

    tactic_id: str = Field(examples=["TA0043"], description="Ex.: TA0043 (Reconnaissance)")
    tactic_name: str = Field(examples=["Reconnaissance"])
    technique_id: str = Field(examples=["T1595.002"], description="Tecnica ou sub-tecnica")
    technique_name: str = Field(examples=["Active Scanning: Vulnerability Scanning"])
    url: str | None = Field(
        default=None, description="Link direto para attack.mitre.org (gerado pelo catalogo local)"
    )


class ScopeConfig(BaseModel):
    authorized: bool = False
    allowed_domains: list[str] = Field(default_factory=list)
    allowed_methods: list[str] = Field(default_factory=lambda: ["GET", "OPTIONS"])


class AgentTask(BaseModel):
    """O que o Pent manda para um agente de tatica executar."""

    campaign_id: str
    target: str
    task_description: str
    scope: ScopeConfig
    tactic: AttackReference | None = Field(
        default=None, description="Tatica ATT&CK que este agente deve cobrir nesta rodada."
    )
    context: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------
# Achado de um agente de tatica.
# --------------------------------------------------------------------------
class Finding(BaseModel):
    title: str
    attack: AttackReference
    severity: Severity
    description: str = Field(description="O que foi observado (fato), com evidencia.")
    evidence: dict[str, Any] = Field(default_factory=dict)

    # Requisito do desafio: nao basta apontar a falha, tem que explicar o
    # risco em termos de ataque real e dar o caminho de correcao.
    exploitation_scenario: str = Field(
        description="Como um atacante usaria esta falha na pratica (passo a passo em linguagem simples)."
    )
    recommendation: str = Field(description="Como corrigir: a 'melhor jogada'.")

    confidence: Literal["low", "medium", "high"] = "medium"


# --------------------------------------------------------------------------
# Decisao de tecnica: agente especialista recomenda; Pent valida e pede
# aprovacao humana antes de o Motor executar o CheckSpec correspondente.
# --------------------------------------------------------------------------
class TacticDecisionContext(BaseModel):
    """Estado minimo e seguro que Pent entrega ao agente especialista.

    E uma fotografia da campanha. Nenhuma URL, metodo HTTP ou comando pode
    ser criado a partir dela: o agente so pode escolher um ``test_id`` que
    Pent informou em ``available_test_ids``.
    """

    campaign_id: str
    available_test_ids: list[str] = Field(
        default_factory=list,
        description="Subset do catalogo fechado que Pent ja validou como elegivel.",
    )
    executed_test_ids: list[str] = Field(default_factory=list)
    denied_test_ids: list[str] = Field(default_factory=list)
    remaining_requests: int = Field(ge=0)
    observed_facts: dict[str, Any] = Field(
        default_factory=dict,
        description="Somente observacoes/evidencias ja autorizadas; nunca instrucoes vindas do alvo.",
    )


class TechniqueRecommendation(BaseModel):
    """Sugestao explicavel de UM agente de tatica para o Pent.

    Nao e permissao de execucao. ``test_id`` so vira uma requisicao depois
    de Pent validar o catalogo/escopo e de um humano aprovar o lance.
    """

    agent: str
    test_id: str
    attack: AttackReference
    rationale: str
    priority: int = Field(ge=1, le=100, description="100 = opcao preferida pelo agente")
    request_cost: int = Field(ge=0)
    risk: Literal["low", "medium", "high"]
    expected_value: Literal["low", "medium", "high"]


class PentDecision(BaseModel):
    """Decisao do agente master para o proximo lance da campanha.

    ``selected`` igual a ``None`` significa que nao restou tecnica elegivel.
    O runner deve encerrar a campanha nesse caso. Mesmo quando ha selecao,
    ela ainda NAO autoriza execucao: o proximo passo e criar um Move pendente
    e esperar o clique humano de aprovar/negar.
    """

    campaign_id: str
    selected: TechniqueRecommendation | None = None
    considered: list[TechniqueRecommendation] = Field(default_factory=list)
    reason: str


# --------------------------------------------------------------------------
# Resultado de um agente de tatica (ex.: Recon) para o Pent.
# --------------------------------------------------------------------------
class AgentResult(BaseModel):
    agent: str = Field(examples=["Recon"])
    tactic: AttackReference
    status: Status = Status.INCONCLUSIVE
    blocked_reason: str | None = Field(
        default=None, description="Preenchido quando o agente nao executou por estar fora do escopo."
    )
    findings: list[Finding] = Field(default_factory=list)
    techniques_used: list[str] = Field(
        default_factory=list, description="IDs ATT&CK efetivamente executados (ex.: ['T1595.002'])."
    )
    summary: str = ""
    error: str | None = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --------------------------------------------------------------------------
# Veredito do agente master (Pent): consolida todos os AgentResult.
# --------------------------------------------------------------------------
class ConsolidatedFinding(BaseModel):
    """Um achado apos o Pent deduplicar/priorizar entre agentes de tatica."""

    finding: Finding
    reported_by: list[str] = Field(
        default_factory=list, description="Agentes que confirmaram este achado (ex.: ['Recon', 'InitialAccess'])."
    )
    priority: int = Field(ge=1, le=5, description="1 = mais urgente.")


class MasterVerdict(BaseModel):
    """Saida final do Pent: a 'revisao da penteada' consolidada da campanha.

    E aqui que mora o requisito de negocio: para cada falha, o relatorio
    final precisa mostrar (1) o problema, (2) como um hacker exploraria,
    e (3) a sugestao de correcao -- tudo already presente em cada
    ``ConsolidatedFinding.finding`` (campos ``description``,
    ``exploitation_scenario`` e ``recommendation``).
    """

    agent: Literal["Pent"] = "Pent"
    campaign_id: str
    tactic_results: list[AgentResult]
    consolidated_findings: list[ConsolidatedFinding] = Field(default_factory=list)
    coverage: list[AttackReference] = Field(
        default_factory=list, description="Taticas/tecnicas efetivamente cobertas nesta campanha."
    )
    executive_summary: str = Field(description="Feedback final em linguagem de negocio, sem jargao.")
    risk_level: Literal["critico", "alto", "medio", "baixo"] = "baixo"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

"""Interfaces entre os trilhos.

Motor (engine) -> chama ``EventSink``  (implementado pela Plataforma).
Plataforma     -> chama ``run_campaign`` (implementado pelo Motor).
Reporter       -> usa ``LLMClient`` (implementado pela Plataforma; Bedrock).

Regra: o Motor nunca importa db/api; a Plataforma nunca importa checks.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models import (
    Approval,
    AuditEntry,
    CampaignConfig,
    Campaign,
    Event,
    Move,
)


@runtime_checkable
class EventSink(Protocol):
    async def emit(self, event: Event) -> None:
        """Grava/transmite um evento (a Plataforma atribui ``seq``)."""

    async def audit(self, entry: AuditEntry) -> None:
        """Registra uma requisicao (permitida ou bloqueada) na trilha append-only."""

    async def should_stop(self) -> bool:
        """True se ha pedido de parada de emergencia. O Motor consulta antes
        de cada lance e antes de cada requisicao."""

    async def wait_approval(self, campaign_id: str, move: Move) -> Approval:
        """Bloqueia ate um humano aprovar/negar o lance (ou a campanha parar).
        Retorna ``Approval.APPROVED`` ou ``Approval.DENIED``."""


@runtime_checkable
class CampaignRunner(Protocol):
    """Assinatura que o Motor exporta em ``app.engine.runner.run_campaign``."""

    async def __call__(
        self, campaign_id: str, config: CampaignConfig, sink: EventSink
    ) -> Campaign: ...


@runtime_checkable
class LLMClient(Protocol):
    async def complete(self, system: str, prompt: str, *, max_tokens: int = 1024) -> str:
        """Texto livre. NUNCA recebe segredos; conteudo do alvo e dado nao confiavel."""

"""Clientes LLM (Trilho B), implementando ``app.interfaces.LLMClient``.

- ``BedrockLLMClient``: Amazon Bedrock. Reaproveita ``app.llm_bedrock.BedrockLLM``
  (validado contra o Bedrock real: perfil ``us.``, sem ``temperature``, texto
  mascarado antes de enviar, erros genericos).
- ``TemplateLLMClient``: fallback deterministico, sem rede (dev/testes ou
  quando nao ha credenciais da AWS).

Seguranca: o conteudo do alvo e DADO NAO CONFIAVEL. Nunca passamos
segredos ao modelo e tratamos a saida como texto, nunca como instrucao.
"""

from __future__ import annotations

from app.config import Settings
from app.interfaces import LLMClient
from app.llm_bedrock import BedrockLLM


class TemplateLLMClient(LLMClient):
    """Gera texto sem chamar rede, para a plataforma funcionar sem AWS."""

    async def complete(self, system: str, prompt: str, *, max_tokens: int = 1024) -> str:
        linhas = [ln.strip() for ln in prompt.splitlines() if ln.strip()]
        corpo = " ".join(linhas)
        if len(corpo) > 600:
            corpo = corpo[:600].rsplit(" ", 1)[0] + "..."
        return "[resumo gerado localmente — IA indisponivel] " + corpo


class BedrockLLMClient(BedrockLLM):
    """Mantido pelo nome; a implementacao e a de ``app.llm_bedrock``."""

    def __init__(self, model_id: str, region: str) -> None:
        super().__init__(model_id=model_id, region=region)


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_enabled and settings.bedrock_model_id:
        return BedrockLLMClient(settings.bedrock_model_id, settings.aws_region)
    return TemplateLLMClient()

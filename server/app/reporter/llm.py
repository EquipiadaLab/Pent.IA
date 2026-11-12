"""Clientes LLM (Trilho B), implementando ``app.interfaces.LLMClient``.

- ``BedrockLLMClient``: Amazon Bedrock via Converse API (boto3).
- ``TemplateLLMClient``: fallback deterministico, sem rede, usado quando
  ``BEDROCK_MODEL_ID`` nao esta configurado (dev/demo e testes).

Seguranca: o conteudo do alvo e DADO NAO CONFIAVEL. Nunca passamos
segredos ao modelo e tratamos a saida como texto, nunca como instrucao.
"""

from __future__ import annotations

import asyncio

from app.config import Settings
from app.interfaces import LLMClient


class TemplateLLMClient(LLMClient):
    """Gera texto sem chamar rede. Ecoa o prompt de forma resumida para que
    a plataforma funcione ponta a ponta sem credenciais da AWS."""

    async def complete(self, system: str, prompt: str, *, max_tokens: int = 1024) -> str:
        linhas = [ln.strip() for ln in prompt.splitlines() if ln.strip()]
        corpo = " ".join(linhas)
        if len(corpo) > 600:
            corpo = corpo[:600].rsplit(" ", 1)[0] + "..."
        return (
            "[resumo gerado localmente — configure BEDROCK_MODEL_ID para usar o LLM] "
            + corpo
        )


class BedrockLLMClient(LLMClient):
    def __init__(self, model_id: str, region: str) -> None:
        self._model_id = model_id
        self._region = region
        self._client = None  # criado sob demanda (lazy)

    def _ensure_client(self):
        if self._client is None:
            import boto3  # import tardio: so quando realmente for usar Bedrock

            self._client = boto3.client("bedrock-runtime", region_name=self._region)
        return self._client

    async def complete(self, system: str, prompt: str, *, max_tokens: int = 1024) -> str:
        return await asyncio.to_thread(self._invoke, system, prompt, max_tokens)

    def _invoke(self, system: str, prompt: str, max_tokens: int) -> str:
        client = self._ensure_client()
        resp = client.converse(
            modelId=self._model_id,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0.2},
        )
        parts = resp["output"]["message"]["content"]
        return "".join(p.get("text", "") for p in parts).strip()


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_enabled and settings.bedrock_model_id:
        return BedrockLLMClient(settings.bedrock_model_id, settings.aws_region)
    return TemplateLLMClient()

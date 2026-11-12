"""Chamada ao LLM que DEVE responder JSON. Toda saida da IA passa por aqui.

A resposta e extraida, parseada e validada por quem chama (schema/allowlist).
Qualquer falha devolve ``None``: quem chama usa o plano B deterministico.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.interfaces import LLMClient


def extract_json(raw: str) -> Any:
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except ValueError:
        return None


async def ask_json(llm: LLMClient, system: str, prompt: str, *, max_tokens: int = 1024,
                   timeout_s: float = 60.0) -> dict | None:
    try:
        raw = await asyncio.wait_for(llm.complete(system, prompt, max_tokens=max_tokens), timeout_s)
    except Exception:  # noqa: BLE001 - IA e opcional; o chamador tem plano B
        return None
    data = extract_json(raw)
    return data if isinstance(data, dict) else None


def clip(value: Any, limit: int = 400) -> str | None:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value[:limit] or None

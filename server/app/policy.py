"""Pre-aprovacao de testes sensiveis para execucoes AUTOMATICAS (ex.: todo dia as 9h).

Definida SO no servidor (.env), por um humano responsavel. A tela ou o n8n nao
conseguem ampliar: so pedem ``unattended=true``, e o que nao estiver aqui e negado.

    PREAPPROVED_TESTS=FILE-001,FILE-002,ERR-001
    PREAPPROVED_BY=Maria Souza (CISO)
    PREAPPROVED_UNTIL=2026-11-30
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, time


@dataclass(frozen=True)
class PolicyDecision:
    approved: bool
    actor: str
    reason: str


def _until() -> datetime | None:
    raw = os.getenv("PREAPPROVED_UNTIL", "").strip()
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if value.tzinfo is None:
        if len(raw) <= 10:  # so a data: vale ate o fim do dia
            value = datetime.combine(value.date(), time.max)
        value = value.replace(tzinfo=UTC)
    return value


def preapproval(test_id: str, now: datetime | None = None) -> PolicyDecision:
    now = now or datetime.now(UTC)
    tests = {t.strip() for t in os.getenv("PREAPPROVED_TESTS", "").split(",") if t.strip()}
    by = os.getenv("PREAPPROVED_BY", "").strip()
    until = _until()
    if test_id not in tests:
        return PolicyDecision(False, "politica do servidor", "teste sem pre-aprovacao; negado na execucao automatica")
    if not by or until is None:
        return PolicyDecision(False, "politica do servidor", "pre-aprovacao incompleta (falta PREAPPROVED_BY/UNTIL)")
    if now > until:
        return PolicyDecision(False, "politica do servidor", f"pre-aprovacao vencida em {until:%d/%m/%Y}")
    return PolicyDecision(True, f"pre-aprovado por {by} (valido ate {until:%d/%m/%Y})", "pre-aprovacao vigente")

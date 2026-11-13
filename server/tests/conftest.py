"""Deixa cada teste comecar com o alvo em estado neutro (modo aberto),
independente do .env local. Testes que precisam travar/listar alvo fazem
seu proprio monkeypatch.setenv depois."""

import pytest


@pytest.fixture(autouse=True)
def _clean_target_env(monkeypatch):
    for var in ("LOCKED_TARGET", "AUTHORIZED_TARGETS", "DEFAULT_TARGET"):
        monkeypatch.delenv(var, raising=False)

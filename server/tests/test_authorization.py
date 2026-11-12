"""Controle de alvo: modo lista fixa, modo aberto e anti-SSRF."""

import pytest

from app.authorization import authorization_error, default_target, is_authorized


def test_locked_target_only_allows_that_target(monkeypatch):
    monkeypatch.setenv("LOCKED_TARGET", "https://3.migbot.com.br")
    assert is_authorized("https://3.migbot.com.br")
    assert is_authorized("https://3.migbot.com.br/qualquer/caminho")  # mesma origem
    assert not is_authorized("https://outro.com")
    assert not is_authorized("http://127.0.0.1:8080")  # ate localhost e recusado
    assert "travado" in (authorization_error("https://outro.com") or "")


def test_locked_target_wins_over_authorized_list(monkeypatch):
    monkeypatch.setenv("LOCKED_TARGET", "https://3.migbot.com.br")
    monkeypatch.setenv("AUTHORIZED_TARGETS", "https://outro.com")
    assert is_authorized("https://3.migbot.com.br")
    assert not is_authorized("https://outro.com")


def test_strict_mode_only_allows_listed(monkeypatch):
    monkeypatch.setenv("AUTHORIZED_TARGETS", "https://alvo.com")
    assert is_authorized("https://alvo.com/x")
    assert not is_authorized("https://outro.com")  # fora da lista
    assert "fora da lista" in (authorization_error("https://outro.com") or "")


def test_open_mode_allows_public_and_loopback(monkeypatch):
    monkeypatch.delenv("AUTHORIZED_TARGETS", raising=False)
    assert is_authorized("http://127.0.0.1:8080")  # site de treino
    assert is_authorized("http://localhost:8080")
    assert is_authorized("https://example.com")  # host publico resolvivel


def test_open_mode_blocks_private_and_metadata(monkeypatch):
    monkeypatch.delenv("AUTHORIZED_TARGETS", raising=False)
    for url in ("http://169.254.169.254/latest/meta-data/",  # metadados da nuvem
                "http://10.0.0.5", "http://192.168.0.1", "http://172.31.42.219"):
        err = authorization_error(url)
        assert err is not None and "interna" in err, url


def test_open_mode_blocks_unresolvable(monkeypatch):
    monkeypatch.delenv("AUTHORIZED_TARGETS", raising=False)
    assert not is_authorized("https://nao-existe.invalid")


def test_block_private_can_be_disabled(monkeypatch):
    monkeypatch.delenv("AUTHORIZED_TARGETS", raising=False)
    monkeypatch.setenv("BLOCK_PRIVATE_TARGETS", "false")
    assert is_authorized("http://10.0.0.5")


def test_default_target(monkeypatch):
    monkeypatch.delenv("DEFAULT_TARGET", raising=False)
    assert default_target() == "https://3.migbot.com.br"
    monkeypatch.setenv("DEFAULT_TARGET", "exemplo.com")
    assert default_target() == "https://exemplo.com"  # adiciona esquema
    monkeypatch.setenv("DEFAULT_TARGET", "http://exemplo.com")
    assert default_target() == "http://exemplo.com"


def test_invalid_url(monkeypatch):
    monkeypatch.delenv("AUTHORIZED_TARGETS", raising=False)
    assert "invalida" in (authorization_error("ftp://x") or "")

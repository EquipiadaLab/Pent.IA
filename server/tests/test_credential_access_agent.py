"""Testes do CredentialAccessAgent (TA0006) e do check CREDS-SQLI-LOGIN-001."""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.agents.CredentialAccess.catalog import CREDENTIAL_ACCESS_TECHNIQUES
from app.agents.CredentialAccess.credential_access_agent import CredentialAccessAgent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.engine.checks import CATALOG_BY_ID
from app.engine.memory_sink import MemorySink
from app.engine.runner import run_campaign
from app.engine.scope import ScopeGuard, utcnow
from app.models import Approval, CampaignConfig, Status
from app.schemas.agents_contract import AttackReference, TacticDecisionContext


def _context(**overrides) -> TacticDecisionContext:
    data = {
        "campaign_id": "campaign-credential-access",
        "available_test_ids": ["CREDS-SQLI-LOGIN-001"],
        "executed_test_ids": [],
        "denied_test_ids": [],
        "remaining_requests": 10,
        "observed_facts": {"origin_scheme": "https"},
    }
    data.update(overrides)
    return TacticDecisionContext(**data)


def _reference() -> AttackReference:
    return AttackReference(
        tactic_id="TA0006",
        tactic_name="Credential Access",
        technique_id="T1212",
        technique_name="Exploitation for Credential Access",
        url="https://attack.mitre.org/techniques/T1212/",
    )


def test_catalogo_cobre_apenas_t1212() -> None:
    assert [(item.test_id, item.technique_id) for item in CREDENTIAL_ACCESS_TECHNIQUES] == [
        ("CREDS-SQLI-LOGIN-001", "T1212")
    ]


def test_check_exige_aprovacao_humana() -> None:
    assert CATALOG_BY_ID["CREDS-SQLI-LOGIN-001"].needs_approval is True


def test_recomenda_o_check_disponivel(monkeypatch) -> None:
    agent = CredentialAccessAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    recommendations = agent.recommend(_context())

    assert len(recommendations) == 1
    item = recommendations[0]
    assert item.agent == "CredentialAccess"
    assert item.test_id == "CREDS-SQLI-LOGIN-001"
    assert item.attack.technique_id == "T1212"


def test_ignora_ids_fora_do_catalogo_do_motor(monkeypatch) -> None:
    agent = CredentialAccessAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(available_test_ids=["TLS-001"])) == []


@pytest.mark.parametrize("field", ["executed_test_ids", "denied_test_ids"])
def test_nao_recomenda_check_ja_resolvido_ou_negado(monkeypatch, field: str) -> None:
    agent = CredentialAccessAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(**{field: ["CREDS-SQLI-LOGIN-001"]})) == []


def test_catalogo_mitre_ausente_nao_cria_referencia_falsa(monkeypatch) -> None:
    agent = CredentialAccessAgent()

    def unavailable(_: str) -> AttackReference:
        raise AttackCatalogUnavailable("cache ausente")

    monkeypatch.setattr(agent, "attack_reference", unavailable)

    assert agent.recommend(_context()) == []


def test_nome_e_tatica_seguem_o_padrao_dos_outros_agentes() -> None:
    agent = CredentialAccessAgent()
    assert agent.name == "CredentialAccess"
    assert agent.tactic_id == "TA0006"


# --------------------------------------------------------------------------
# Scope Guard: a exceção de metodo e estreita (so POST /rest/user/login).
# --------------------------------------------------------------------------
def test_scope_guard_bloqueia_post_em_outras_rotas():
    config = CampaignConfig(origin="https://alvo.exemplo", authorized_by="x", authorized_at=utcnow())
    guard = ScopeGuard(config)
    assert not guard.authorize("POST", "https://alvo.exemplo/outra-rota").allowed


def test_scope_guard_permite_post_apenas_no_login():
    config = CampaignConfig(origin="https://alvo.exemplo", authorized_by="x", authorized_at=utcnow())
    guard = ScopeGuard(config)
    assert guard.authorize("POST", "https://alvo.exemplo/rest/user/login").allowed


# --------------------------------------------------------------------------
# Check CREDS-SQLI-LOGIN-001: servidor fake simula login vulneravel/seguro.
# --------------------------------------------------------------------------
@pytest.fixture
def vulnerable_login():
    """Simula um login que aceita o payload classico de bypass por SQLi."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8") if length else "{}"
            data = json.loads(raw) if raw else {}
            body: bytes
            if data.get("email") == "' OR 1=1--":
                body = json.dumps({"authentication": {"token": "eyJhbGciOiJIUzI1NiJ9.fake.sig"}}).encode()
            else:
                body = json.dumps({"error": "invalid credentials"}).encode()
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def safe_login():
    """Simula um login parametrizado que rejeita o payload de bypass."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            body = json.dumps({"error": "invalid credentials"}).encode()
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _run_login_bypass_only(origin: str, *, approve: bool):
    config = CampaignConfig(
        origin=origin,
        authorized_by="teste-local",
        authorized_at=utcnow(),
        only_tests=["CREDS-SQLI-LOGIN-001"],
        max_requests_per_second=100,
    )
    sink = MemorySink(approve=approve)
    campaign = asyncio.run(run_campaign("creds-sqli", config, sink))
    assert len(campaign.moves) == 1
    return campaign.moves[0], sink


def test_bypass_confirmado_quando_token_e_emitido(vulnerable_login):
    move, sink = _run_login_bypass_only(vulnerable_login, approve=True)

    assert move.approval is Approval.APPROVED
    assert move.status is Status.FAIL
    assert "bypass" in move.explanation.lower()
    # O token JWT nunca aparece na evidencia nem na auditoria.
    assert all("eyJ" not in (a.url or "") for a in sink.audits)
    assert move.evidence and all("eyJ" not in (ev.note or "") for ev in move.evidence)


def test_sem_bypass_quando_login_rejeita_payload(safe_login):
    move, _sink = _run_login_bypass_only(safe_login, approve=True)

    assert move.status is Status.PASS


def test_login_bypass_nao_executa_sem_aprovacao_humana(vulnerable_login):
    move, sink = _run_login_bypass_only(vulnerable_login, approve=False)

    assert move.approval is Approval.DENIED
    assert move.status is None
    assert len(sink.audits) == 0

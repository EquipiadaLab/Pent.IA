"""Testes do ExecutionAgent (TA0002) e do check EXEC-SSTI-001."""

from __future__ import annotations

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from app.agents.Execution.catalog import EXECUTION_TECHNIQUES
from app.agents.Execution.execution_agent import ExecutionAgent
from app.attack_mitre.catalog import AttackCatalogUnavailable
from app.engine.checks import CATALOG_BY_ID
from app.engine.memory_sink import MemorySink
from app.engine.runner import run_campaign
from app.engine.scope import utcnow
from app.models import Approval, CampaignConfig, Status
from app.schemas.agents_contract import AttackReference, TacticDecisionContext


def _context(**overrides) -> TacticDecisionContext:
    data = {
        "campaign_id": "campaign-execution",
        "available_test_ids": ["EXEC-SSTI-001"],
        "executed_test_ids": [],
        "denied_test_ids": [],
        "remaining_requests": 10,
        "observed_facts": {"origin_scheme": "https"},
    }
    data.update(overrides)
    return TacticDecisionContext(**data)


def _reference() -> AttackReference:
    return AttackReference(
        tactic_id="TA0002",
        tactic_name="Execution",
        technique_id="T1190",
        technique_name="Exploit Public-Facing Application",
        url="https://attack.mitre.org/techniques/T1190/",
    )


def test_catalogo_cobre_apenas_t1190() -> None:
    assert [(item.test_id, item.technique_id) for item in EXECUTION_TECHNIQUES] == [
        ("EXEC-SSTI-001", "T1190")
    ]


def test_check_exige_aprovacao_humana() -> None:
    assert CATALOG_BY_ID["EXEC-SSTI-001"].needs_approval is True


def test_recomenda_o_check_disponivel(monkeypatch) -> None:
    agent = ExecutionAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    recommendations = agent.recommend(_context())

    assert len(recommendations) == 1
    item = recommendations[0]
    assert item.agent == "Execution"
    assert item.test_id == "EXEC-SSTI-001"
    assert item.attack.technique_id == "T1190"
    assert item.risk == "medium"


def test_ignora_ids_fora_do_catalogo_do_motor(monkeypatch) -> None:
    agent = ExecutionAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(available_test_ids=["TLS-001"])) == []


@pytest.mark.parametrize("field", ["executed_test_ids", "denied_test_ids"])
def test_nao_recomenda_check_ja_resolvido_ou_negado(monkeypatch, field: str) -> None:
    agent = ExecutionAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(**{field: ["EXEC-SSTI-001"]})) == []


def test_respeita_orcamento_de_requisicao(monkeypatch) -> None:
    agent = ExecutionAgent()
    monkeypatch.setattr(agent, "attack_reference", lambda _: _reference())

    assert agent.recommend(_context(remaining_requests=2)) == []
    assert agent.recommend(_context(remaining_requests=3)) != []


def test_catalogo_mitre_ausente_nao_cria_referencia_falsa(monkeypatch) -> None:
    agent = ExecutionAgent()

    def unavailable(_: str) -> AttackReference:
        raise AttackCatalogUnavailable("cache ausente")

    monkeypatch.setattr(agent, "attack_reference", unavailable)

    assert agent.recommend(_context()) == []


def test_nome_e_tatica_seguem_o_padrao_dos_outros_agentes() -> None:
    agent = ExecutionAgent()
    assert agent.name == "Execution"
    assert agent.tactic_id == "TA0002"


# --------------------------------------------------------------------------
# Check EXEC-SSTI-001: servidor fake simula motor de template vulneravel.
# --------------------------------------------------------------------------
@pytest.fixture
def vulnerable_search():
    """Simula um endpoint de busca que AVALIA expressoes de template."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            query = parse_qs(urlsplit(self.path).query)
            q = query.get("q", [""])[0]
            # Simula um motor de template avaliando "${{7*7}}", "#{7*7}" etc.
            if q in ("${{7*7}}", "#{7*7}", "{{7*7}}"):
                body = b'{"data": [{"name": "49"}]}'
            else:
                body = b'{"data": []}'
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
def safe_search():
    """Simula um endpoint de busca que NAO avalia a expressao (so ecoa/ignora)."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            body = b'{"data": []}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _run_ssti_only(origin: str, *, approve: bool):
    config = CampaignConfig(
        origin=origin,
        authorized_by="teste-local",
        authorized_at=utcnow(),
        only_tests=["EXEC-SSTI-001"],
        max_requests_per_second=100,
    )
    sink = MemorySink(approve=approve)
    campaign = asyncio.run(run_campaign("exec-ssti", config, sink))
    assert len(campaign.moves) == 1
    return campaign.moves[0], sink


def test_ssti_detectado_quando_servidor_avalia_expressao(vulnerable_search):
    move, sink = _run_ssti_only(vulnerable_search, approve=True)

    assert move.approval is Approval.APPROVED
    assert move.status is Status.FAIL
    assert "avaliou" in move.explanation.lower()
    assert move.evidence
    # Sem exploracao destrutiva: apenas GET foi usado.
    assert all(a.method == "GET" for a in sink.audits)


def test_ssti_nao_detectado_quando_servidor_nao_avalia(safe_search):
    move, _sink = _run_ssti_only(safe_search, approve=True)

    assert move.status is Status.PASS


def test_ssti_nao_executa_sem_aprovacao_humana(vulnerable_search):
    move, sink = _run_ssti_only(vulnerable_search, approve=False)

    assert move.approval is Approval.DENIED
    assert move.status is None
    assert len(sink.audits) == 0

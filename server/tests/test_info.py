"""Endpoints de status e informacao: /status, /catalog, /scope, /campaigns/{id}/status."""

import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "devtools"))
import lab_server  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'i.db'}")
    monkeypatch.setenv("LLM_ENABLED", "false")
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def lab():
    srv, url = lab_server.start()
    yield url
    srv.shutdown()


def test_status_reports_components(client):
    r = client.get("/status")
    assert r.status_code == 200
    s = r.json()
    assert s["status"] == "ok" and s["engine_mode"] == "real"
    assert s["components"]["api"]["status"] == "ok"
    assert s["components"]["database"]["status"] == "ok"
    assert s["components"]["llm"]["status"] == "disabled"
    assert s["campaigns"]["total"] == 0 and "running" in s["campaigns"]
    text = r.text.lower()
    assert "aws_secret" not in text and "akia" not in text  # nada de credencial


def test_status_check_llm_never_leaks(client, monkeypatch):
    class Boom:
        async def complete(self, *a, **k):
            raise RuntimeError("arn:aws:iam::123456789012:role/x AKIAABCDEFGHIJKLMNOP")

    app = client.app
    app.state.ctx.report_builder._llm = Boom()
    object.__setattr__(app.state.ctx.settings, "bedrock_model_id", "x")  # finge IA ligada
    llm = client.get("/status?check_llm=true").json()["components"]["llm"]
    assert llm["status"] == "error" and "RuntimeError" in llm["detail"]
    assert "AKIA" not in llm["detail"] and "arn:" not in llm["detail"]


def test_catalog(client):
    cat = client.get("/catalog").json()
    assert len(cat) == 14
    git = next(t for t in cat if t["test_id"] == "FILE-001")
    assert git["needs_approval"] is True and git["hypothesis"] and git["impact"]


def test_scope(client, monkeypatch):
    monkeypatch.setenv("AUTHORIZED_TARGETS", "https://alvo.com")
    monkeypatch.setenv("PREAPPROVED_TESTS", "FILE-001,ERR-001")
    monkeypatch.setenv("PREAPPROVED_BY", "Maria")
    monkeypatch.setenv("PREAPPROVED_UNTIL", (datetime.now(UTC) + timedelta(days=2)).date().isoformat())
    s = client.get("/scope").json()
    assert s["authorized_targets"] == ["https://alvo.com:443"] and s["accepts_any_target"] is False
    assert s["default_target"] is None and s["blocks_private_targets"] is True
    assert s["allowed_methods"] == ["GET", "OPTIONS"] and s["blocked_profiles"] == ["intrusive"]
    assert s["preapproval"]["active"] == ["FILE-001", "ERR-001"]
    monkeypatch.delenv("AUTHORIZED_TARGETS")
    open_scope = client.get("/scope").json()
    assert open_scope["accepts_any_target"] is True and open_scope["default_target"]


def test_campaign_status_progress_and_pending(client, lab):
    cid = client.post("/campaigns", json={"config": {"origin": lab, "authorized_by": "Org",
                                                     "authorized_at": "2026-11-12T15:00:00Z",
                                                     "max_requests_per_second": 5}}).json()["id"]
    saw_pending = False
    for _ in range(600):
        st = client.get(f"/campaigns/{cid}/status").json()
        if st["pending_approvals"]:
            saw_pending = True
            p = st["pending_approvals"][0]
            assert st["current_move"]["stage"] == "awaiting_approval" and p["hypothesis"]
            client.post(f"/campaigns/{cid}/moves/{p['move']}/approve")
        if st["state"] in ("finished", "stopped", "failed"):
            break
        time.sleep(0.05)
    assert saw_pending
    assert st["progress"] == {"played": 14, "total": 14, "percent": 100}
    assert st["current_move"] is None and st["score"]["accuracy"] < 40
    assert st["last_seq"] == client.get(f"/campaigns/{cid}/events").json()[-1]["seq"]
    assert client.get("/campaigns/nao-existe/status").status_code == 404
    assert client.get("/status").json()["campaigns"]["finished"] == 1

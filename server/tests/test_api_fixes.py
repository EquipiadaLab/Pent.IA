"""Correcoes da API sem mudar caminhos: aprovacao, duplicidade, estado, limites e IA por lance."""

import asyncio
import json
import sys
import time
from collections import Counter
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "devtools"))
import lab_server  # noqa: E402

from app.explainer import explain_moves, validate_citations  # noqa: E402
from app.models import Campaign, CampaignConfig, Evidence, Move, Phase, Profile, Status, Grade, Severity  # noqa: E402

NOW = "2026-11-12T15:00:00Z"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 't.db'}")
    monkeypatch.setenv("LLM_ENABLED", "false")
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def lab():
    srv, url = lab_server.start()
    yield url
    srv.shutdown()


def _create(c, origin, **extra):
    r = c.post("/campaigns", json={"config": {"origin": origin, "authorized_by": "Org",
                                              "authorized_at": NOW, "max_requests_per_second": 5, **extra}})
    assert r.status_code == 201, r.text
    return r.json()


def test_locked_target_overrides_and_refuses_others(client, lab, monkeypatch):
    monkeypatch.setenv("LOCKED_TARGET", lab)  # trava no alvo de treino (alcancavel)
    # front manda outro endereco -> 403, mesmo sendo uma URL valida
    r = client.post("/campaigns", json={"config": {"origin": "https://outro.com",
                                                   "authorized_by": "x", "authorized_at": NOW}})
    assert r.status_code == 403 and "travado" in r.json()["detail"].lower()
    # front manda vazio -> usa o alvo travado
    r2 = client.post("/campaigns", json={"config": {"authorized_by": "x", "authorized_at": NOW}})
    assert r2.status_code == 201 and r2.json()["config"]["origin"] == lab
    client.post(f"/campaigns/{r2.json()['id']}/stop")


def _wait(c, cid, approve=True, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        cam = c.get(f"/campaigns/{cid}").json()
        for m in cam["moves"]:
            if m["approval"] == "pending":
                c.post(f"/campaigns/{cid}/moves/{m['move']}/{'approve' if approve else 'deny'}")
        if cam["state"] in ("finished", "stopped", "failed"):
            return cam
        time.sleep(0.05)
    raise AssertionError("campanha nao terminou")


def test_approved_moves_keep_result_and_events_not_duplicated(client, lab):
    cid = _create(client, lab)["id"]
    cam = _wait(client, cid)
    by = {m["test_id"]: m for m in cam["moves"]}
    for tid in ("FILE-001", "FILE-002", "ERR-001"):
        assert by[tid]["approval"] == "approved"
        assert by[tid]["grade"] is not None, f"{tid} perdeu o resultado"
    ev = client.get(f"/campaigns/{cid}/events").json()
    counts = Counter(e["type"] for e in ev)
    assert counts["approval_requested"] == 3 and counts["approval_resolved"] == 3
    resolved = [e for e in ev if e["type"] == "approval_resolved"]
    assert all(e["data"]["move"] and e["data"]["approval"] == "approved" and e["data"]["actor"] for e in resolved)
    assert all(e["data"].get("move") for e in ev if e["type"] == "approval_requested")
    assert cam["score"] and cam["score"]["accuracy"] < 40


def test_early_approval_does_not_409(client, lab):
    cid = _create(client, lab, max_requests_per_second=0.5)["id"]
    deadline = time.time() + 10
    while time.time() < deadline:
        pend = [m for m in client.get(f"/campaigns/{cid}/moves").json() if m["approval"] == "pending"]
        if pend:
            r = client.post(f"/campaigns/{cid}/moves/{pend[0]['move']}/approve?actor=Ana")
            assert r.status_code == 200, r.text
            break
        time.sleep(0.02)
    client.post(f"/campaigns/{cid}/stop")


def test_denied_and_stop(client, lab):
    cid = _create(client, lab)["id"]
    cam = _wait(client, cid, approve=False)
    denied = [m for m in cam["moves"] if m["approval"] == "denied"]
    assert len(denied) == 3 and all(m["grade"] is None for m in denied)


def test_unauthorized_target_is_failed(client):
    cid = _create(client, "https://example.invalid")["id"]
    time.sleep(0.5)
    cam = client.get(f"/campaigns/{cid}").json()
    assert cam["state"] == "failed" and cam["moves"] == []


def test_server_limits_override_front(client, lab):
    cam = _create(client, lab, allowed_methods=["GET", "DELETE", "POST"],
                  max_requests_per_second=1000, max_total_requests=99999)
    cfg = cam["config"]
    assert cfg["allowed_methods"] == ["GET", "OPTIONS"]
    assert cfg["max_requests_per_second"] <= 5 and cfg["max_total_requests"] <= 500
    client.post(f"/campaigns/{cam['id']}/stop")


def test_cors_and_security_headers(client):
    ok = client.get("/health", headers={"Origin": "http://localhost:5173"})
    bad = client.get("/health", headers={"Origin": "https://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers
    assert ok.headers["x-content-type-options"] == "nosniff"


# ------------------------------------------------------------ explicacao IA
class FakeLLM:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    async def complete(self, system, prompt, *, max_tokens=1024):
        self.prompts.append(prompt)
        return self.reply


def _campaign():
    def mv(n, ev):
        return Move(move=n, test_id=f"T{n}", title=f"Teste {n}", phase=Phase.OPENING, profile=Profile.PASSIVE,
                    status=Status.FAIL, severity=Severity.HIGH, grade=Grade.BLUNDER, explanation="fato",
                    evidence=[Evidence(id=ev, request="GET / HTTP/1.1",
                                       response_headers={"set-cookie": "sid=***"})])
    pend = Move(move=3, test_id="T3", title="Pendente", phase=Phase.ENDGAME, profile=Profile.ACTIVE_LIGHT)
    from datetime import datetime, timezone
    return Campaign(id="c", created_at=datetime.now(timezone.utc), moves=[mv(1, "ev-1-1"), mv(2, "ev-2-1"), pend],
                    config=CampaignConfig(origin="https://a.com", authorized_by="x",
                                          authorized_at=datetime.now(timezone.utc)))


def test_explanations_validate_citations_and_ignore_bad_items():
    reply = json.dumps({"explanations": [
        {"move": 1, "text": "Risco alto [ev-1-1]. Inventado [ev-9-9]. Corrija ja."},
        {"move": 2, "text": "Cita evidencia de outro lance [ev-1-1]."},
        {"move": 3, "text": "lance nao executado"},
        {"move": 99, "text": "nao existe"},
    ]})
    out = asyncio.run(explain_moves(FakeLLM("texto antes " + reply), _campaign()))
    assert out == {1: "Risco alto [ev-1-1]. Corrija ja."}


def test_explanations_survive_llm_failure_and_garbage():
    class Boom:
        async def complete(self, *a, **k):
            raise RuntimeError("AKIAABCDEFGHIJKLMNOP")

    assert asyncio.run(explain_moves(Boom(), _campaign())) == {}
    assert asyncio.run(explain_moves(FakeLLM("nao e json"), _campaign())) == {}


def test_validate_citations():
    assert validate_citations("A [ev-1-1]. B [ev-2-2].", {"ev-1-1"}) == "A [ev-1-1]."

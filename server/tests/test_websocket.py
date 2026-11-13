"""WebSocket ao vivo: mesmo JSON do polling, retomada, origem e campanha inexistente."""

import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "devtools"))
import lab_server  # noqa: E402

from app.engine.checks import CATALOG

NOW = "2026-11-12T15:00:00Z"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ws.db'}")
    monkeypatch.setenv("LLM_ENABLED", "false")
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def lab():
    srv, url = lab_server.start()
    yield url
    srv.shutdown()


def _create(c, origin):
    r = c.post("/campaigns", json={"config": {"origin": origin, "authorized_by": "Org",
                                              "authorized_at": NOW, "max_requests_per_second": 5}})
    return r.json()["id"]


def _auto_approve(c, cid, stop):
    while not stop.is_set():
        for m in c.get(f"/campaigns/{cid}/moves").json():
            if m["approval"] == "pending":
                c.post(f"/campaigns/{cid}/moves/{m['move']}/approve?actor=Ana")
        time.sleep(0.05)


def _receive_all(ws):
    got = []
    while True:
        try:
            got.append(ws.receive_json())
        except WebSocketDisconnect as exc:
            return got, exc.code


def test_ws_streams_same_events_as_polling_and_closes(client, lab):
    cid = _create(client, lab)
    stop = threading.Event()
    t = threading.Thread(target=_auto_approve, args=(client, cid, stop), daemon=True)
    t.start()
    with client.websocket_connect(f"/campaigns/{cid}/ws", headers={"origin": "http://localhost:5173"}) as ws:
        got, code = _receive_all(ws)
    stop.set()
    assert code == 1000
    assert got[-1]["type"] == "campaign_finished"
    assert [e["seq"] for e in got] == sorted(e["seq"] for e in got)
    polled = client.get(f"/campaigns/{cid}/events").json()
    assert got == polled  # JSON identico ao polling
    assert sum(e["type"] == "finding_created" for e in got) == len(CATALOG)


def test_ws_resume_with_since(client, lab):
    cid = _create(client, lab)
    stop = threading.Event()
    threading.Thread(target=_auto_approve, args=(client, cid, stop), daemon=True).start()
    with client.websocket_connect(f"/campaigns/{cid}/ws") as ws:
        _receive_all(ws)
    stop.set()
    with client.websocket_connect(f"/campaigns/{cid}/ws?since=10") as ws:
        got, code = _receive_all(ws)
    assert got and min(e["seq"] for e in got) == 11 and code == 1000


def test_ws_rejects_foreign_origin(client, lab):
    cid = _create(client, lab)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/campaigns/{cid}/ws", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()
    assert exc.value.code == 1008
    client.post(f"/campaigns/{cid}/stop")


def test_ws_unknown_campaign(client):
    with client.websocket_connect("/campaigns/nao-existe/ws") as ws:
        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_json()
    assert exc.value.code == 4404


def test_ws_stop_is_pushed(client, lab):
    cid = _create(client, lab)
    with client.websocket_connect(f"/campaigns/{cid}/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "campaign_started"
        client.post(f"/campaigns/{cid}/stop?")
        got, code = _receive_all(ws)
    types = [e["type"] for e in got]
    assert "stop_requested" in types and types[-1] == "campaign_finished" and code == 1000

"""Agente autonomo dentro de limites: planejamento pela IA, arbitro, confirmacao,
pre-aprovacao, juiz, resumo JSON, revalidacao, comparacao e trilha (itens 3, 5, 7, 8)."""

import asyncio
import json
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "devtools"))
import lab_server  # noqa: E402

from app.comparison import compare  # noqa: E402
from app.engine.memory_sink import MemorySink  # noqa: E402
from app.engine.runner import run_campaign  # noqa: E402
from app.engine.scope import utcnow  # noqa: E402
from app.explainer import apply_explanations, build_summary  # noqa: E402
from app.models import (  # noqa: E402
    Approval, Campaign, CampaignConfig, CampaignState, EventType, Grade, Move, Phase, Profile, Score,
    Severity, Status, Verdict,
)


@pytest.fixture
def lab():
    srv, url = lab_server.start()
    yield url
    srv.shutdown()


def cfg(url, **kw):
    return CampaignConfig(origin=url, authorized_by="Org", authorized_at=utcnow(), max_requests_per_second=200, **kw)


def run(url, sink=None, llm=None, **kw):
    return asyncio.run(run_campaign("c1", cfg(url, **kw), sink or MemorySink(approve=True), llm=llm))


class ScriptedLLM:
    """IA falsa: devolve respostas em sequencia (str) e registra os prompts."""

    def __init__(self, replies):
        self.replies, self.prompts = list(replies), []

    async def complete(self, system, prompt, *, max_tokens=1024):
        self.prompts.append((system, prompt))
        if not self.replies:
            raise RuntimeError("sem resposta")
        r = self.replies.pop(0)
        return r(prompt) if callable(r) else r


def pick(test_id, **extra):
    return json.dumps({"test_id": test_id, "hypothesis": f"hipotese {test_id}", "action": "acao",
                       "expected_result": "esperado", "stop_condition": "parar se sem resposta",
                       "rationale": "motivo", **extra})


# ------------------------------------------------------------- item 3: plano
def test_ai_decides_order_and_plan_is_recorded_before_execution(lab):
    def choose_last(prompt):  # escolhe sempre o ULTIMO teste disponivel (ordem diferente da padrao)
        available = json.loads(prompt)["available_tests"]
        return pick(available[-1]["test_id"])

    sink = MemorySink(approve=True)
    c = run(lab, sink, llm=ScriptedLLM([choose_last] * 14))
    assert [m.test_id for m in c.moves][0] == "ERR-001"  # IA mudou a ordem
    assert len(c.moves) == 14  # cobertura garantida: todos jogados
    assert all(m.plan and m.plan.source == "ai" and m.plan.hypothesis for m in c.moves)
    planned = [e for e in sink.events if e.type is EventType.MOVE_PLANNED]
    assert all(e.move.plan is not None and e.move.status is None for e in planned)  # plano ANTES do resultado


def test_ai_sees_observations_from_the_site(lab):
    llm = ScriptedLLM([lambda p: pick(json.loads(p)["available_tests"][0]["test_id"])] * 14)
    run(lab, llm=llm)
    first = json.loads(llm.prompts[0][1])
    assert first["target"]["observed"]["reachable"] is True
    assert "sid" in first["target"]["observed"]["cookie_names"]
    assert "abc123SESSION" not in llm.prompts[0][1]  # valor do cookie nunca vai para a IA


def test_referee_rejects_out_of_list_choice_and_falls_back(lab):
    llm = ScriptedLLM([pick("HACK-999"), "nao e json"] + [pick("TLS-001")] * 20)
    c = run(lab, llm=llm)
    assert c.moves[0].plan.source == "rules"
    assert len(llm.prompts) == 2  # apos 2 falhas seguidas a IA e desligada nesta partida
    assert all(m.plan.source == "rules" for m in c.moves)
    assert len(c.moves) == 14


def test_without_llm_rules_plan_everything(lab):
    c = run(lab)
    assert all(m.plan and m.plan.source == "rules" and m.plan.expected_result for m in c.moves)


# ------------------------------------------------------------- item 5: confirmacao
def test_findings_are_confirmed_by_second_observation(lab):
    c = run(lab)
    findings = [m for m in c.moves if m.status in (Status.FAIL, Status.WARNING)]
    assert findings and all(m.verdict is Verdict.CONFIRMED for m in findings)
    assert all(m.verdict is None for m in c.moves if m.status is Status.PASS)
    cors = next(m for m in c.moves if m.test_id == "CORS-001")
    assert any(e.id.endswith("-101") for e in cors.evidence)  # evidencia da reconfirmacao
    assert cors.impact and cors.reproduce and cors.reproduce[0].startswith("curl -i")


@pytest.fixture
def flaky():
    """Alvo instavel: 1a resposta sem protecao de clickjacking, 2a com."""
    count = {"n": 0}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            count["n"] += 1
            self.send_response(200)
            if count["n"] % 2 == 0:
                self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_non_reproducible_finding_is_discarded_and_not_scored(flaky):
    c = run(flaky, only_tests=["CLICK-001"])
    m = c.moves[0]
    assert m.status is Status.FAIL and m.verdict is Verdict.DISCARDED
    assert m.grade is Grade.INCONCLUSIVE and "Descartado" in m.explanation
    assert c.score.accuracy == 0 and Grade.BLUNDER not in c.score.counts


# ------------------------------------------------------------- execucao automatica
class NoHumanSink(MemorySink):
    async def wait_approval(self, campaign_id, move):
        raise AssertionError("execucao automatica nao pode esperar humano")


def test_unattended_uses_only_server_preapproval(lab, monkeypatch):
    monkeypatch.setenv("PREAPPROVED_TESTS", "FILE-001")
    monkeypatch.setenv("PREAPPROVED_BY", "Maria (CISO)")
    monkeypatch.setenv("PREAPPROVED_UNTIL", (datetime.now(UTC) + timedelta(days=5)).date().isoformat())
    sink = NoHumanSink()
    c = run(lab, sink, unattended=True)
    by = {m.test_id: m for m in c.moves}
    assert by["FILE-001"].approval is Approval.APPROVED and by["FILE-001"].grade is Grade.BLUNDER
    assert by["FILE-002"].approval is Approval.DENIED and by["FILE-002"].status is None
    resolved = [e for e in sink.events if e.type is EventType.APPROVAL_RESOLVED]
    assert any("Maria (CISO)" in e.data["actor"] for e in resolved)
    assert c.state is CampaignState.FINISHED


def test_unattended_expired_policy_denies(lab, monkeypatch):
    monkeypatch.setenv("PREAPPROVED_TESTS", "FILE-001,FILE-002,ERR-001")
    monkeypatch.setenv("PREAPPROVED_BY", "Maria")
    monkeypatch.setenv("PREAPPROVED_UNTIL", "2020-01-01")
    c = run(lab, NoHumanSink(), unattended=True)
    assert all(m.approval is Approval.DENIED for m in c.moves if m.profile is Profile.ACTIVE_LIGHT
               and m.test_id.startswith(("FILE", "ERR")))


# ------------------------------------------------------------- juiz e resumo JSON
def _camp():
    def mv(n, grade, status, ev):
        from app.models import Evidence
        return Move(move=n, test_id=f"T{n}", title=f"Teste {n}", phase=Phase.OPENING, profile=Profile.PASSIVE,
                    status=status, severity=Severity.HIGH, grade=grade, explanation="fato", impact="impacto",
                    recommendation=f"corrigir {n}",
                    evidence=[Evidence(id=ev, request="GET / HTTP/1.1")])
    return Campaign(id="c", created_at=utcnow(), config=cfg("https://a.com"),
                    score=Score(accuracy=30, eval_bar=-40),
                    moves=[mv(1, Grade.BLUNDER, Status.FAIL, "ev-1-1"), mv(2, Grade.GOOD, Status.PASS, "ev-2-1")])


def test_judge_removes_unsupported_comments():
    coach = ScriptedLLM([json.dumps({"explanations": [{"move": 1, "text": "Grave [ev-1-1]."},
                                                      {"move": 2, "text": "Usa nginx 1.2 vulneravel."}]}),
                         json.dumps({"reviews": [{"move": 1, "verdict": "approved", "issues": []},
                                                 {"move": 2, "verdict": "rejected",
                                                  "issues": ["versao nginx nao esta nos fatos"]}]})])
    c = asyncio.run(apply_explanations(coach, _camp()))
    m1, m2 = c.moves
    assert m1.ai_explanation == "Grave [ev-1-1]." and m1.ai_review.verdict == "approved"
    assert m2.ai_explanation is None and m2.ai_review.verdict == "rejected"
    assert "nginx" in m2.ai_review.issues[0]
    judge_system = coach.prompts[1][0]
    assert "JUIZ" in judge_system


def test_summary_json_validated_and_risk_by_rule():
    reply = json.dumps({"headline": "Site com falha grave [ev-9-9].", "plain_language": "Explicacao simples.",
                        "top_risks": [{"move": 2, "why": "nao e problema"}, {"move": 1, "why": "porque sim"}],
                        "next_steps": ["corrigir 1"], "risk_level": "baixo"})
    s = asyncio.run(build_summary(ScriptedLLM([reply]), _camp()))
    assert s.source == "ai" and s.risk_level == "critico"  # IA nao decide o nivel
    assert [r.move for r in s.top_risks] == [1]  # lance sem problema e filtrado
    assert "ev-9-9" not in s.headline and s.headline  # manchete com citacao falsa trocada pela regra
    assert s.plain_language == "Explicacao simples."
    fb = asyncio.run(build_summary(ScriptedLLM(["lixo"]), _camp()))
    assert fb.source == "rules" and fb.top_risks[0].move == 1


def test_compare_detects_fixed_new_and_still_failing():
    prev, cur = _camp(), _camp()
    cur.id = "d"
    cur.moves[0].status, cur.moves[0].grade = Status.PASS, Grade.BEST
    cur.moves[1].status, cur.moves[1].grade = Status.FAIL, Grade.MISTAKE
    cur.score = Score(accuracy=50, eval_bar=0)
    comp = compare(cur, prev)
    assert comp.fixed == ["T1"] and comp.new == ["T2"] and comp.still_failing == [] and comp.accuracy_delta == 20


# ------------------------------------------------------------- API: revalidacao + trilha
@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'a.db'}")
    monkeypatch.setenv("LLM_ENABLED", "false")
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


def _finish(c, cid):
    for _ in range(600):
        cam = c.get(f"/campaigns/{cid}").json()
        for m in cam["moves"]:
            if m["approval"] == "pending":
                c.post(f"/campaigns/{cid}/moves/{m['move']}/approve?actor=Ana")
        if cam["state"] in ("finished", "stopped", "failed"):
            return cam
        time.sleep(0.05)
    raise AssertionError("nao terminou")


def test_api_revalidation_comparison_and_timeline(client, lab):
    body = {"config": {"origin": lab, "authorized_by": "Org", "authorized_at": "2026-11-12T15:00:00Z",
                       "max_requests_per_second": 5}}
    first = _finish(client, client.post("/campaigns", json=body).json()["id"])
    failed = {m["test_id"] for m in first["moves"] if m["status"] in ("fail", "warning")}

    r = client.post("/campaigns", json={**body, "revalidate_from": first["id"]})
    assert r.status_code == 201 and set(r.json()["config"]["only_tests"]) == failed
    second = _finish(client, r.json()["id"])
    assert {m["test_id"] for m in second["moves"]} == failed

    rep = client.get(f"/campaigns/{second['id']}/report").json()
    assert rep["comparison"]["previous_campaign_id"] == first["id"]
    assert set(rep["comparison"]["still_failing"]) == failed and rep["comparison"]["new"] == []
    assert rep["summary"]["risk_level"] == "critico" and rep["summary"]["top_risks"]
    assert all(m["plan"] and m["reproduce"] is not None for m in rep["campaign"]["moves"])

    tl = client.get(f"/campaigns/{first['id']}/audit").json()
    kinds = {e["kind"] for e in tl}
    assert {"decision", "approval_requested", "approval", "command", "result", "campaign"} <= kinds
    assert [e["at"] for e in tl] == sorted(e["at"] for e in tl)
    assert any("Ana" in e["summary"] for e in tl if e["kind"] == "approval")

    assert client.post("/campaigns", json={**body, "revalidate_from": "nao-existe"}).status_code == 404
    other = {"config": {**body["config"], "origin": "http://127.0.0.1:1"}, "revalidate_from": first["id"]}
    assert client.post("/campaigns", json=other).status_code == 422

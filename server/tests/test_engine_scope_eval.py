import asyncio
from datetime import timedelta

import httpx

from app.engine.evaluator import compute_score, grade_for
from app.engine.executor import Fetcher, classify_error
from app.engine.memory_sink import MemorySink
from app.engine.scope import ScopeGuard, normalize_origin, utcnow
from app.models import CampaignConfig, EventType, Grade, Move, Phase, Profile, Severity, Status


def cfg(**kw) -> CampaignConfig:
    base = dict(origin="https://alvo.com", authorized_by="Org", authorized_at=utcnow())
    return CampaignConfig(**{**base, **kw})


def test_normalize_default_ports():
    assert normalize_origin("https://Alvo.com") == normalize_origin("https://alvo.com:443/x")
    assert normalize_origin("ftp://alvo.com") is None


def test_scope_blocks_other_origin_method_and_userinfo():
    g = ScopeGuard(cfg())
    assert g.authorize("GET", "https://alvo.com/").allowed
    assert not g.authorize("GET", "https://outro.com/").allowed
    assert not g.authorize("GET", "http://alvo.com/").allowed  # esquema diferente
    assert not g.authorize("POST", "https://alvo.com/").allowed
    assert not g.authorize("GET", "https://u:p@alvo.com/").allowed


def test_scope_excluded_path_cannot_be_bypassed():
    g = ScopeGuard(cfg(excluded_paths=["/admin"]))
    assert not g.authorize("GET", "https://alvo.com/admin").allowed
    assert not g.authorize("GET", "https://alvo.com/a/../admin/x").allowed
    assert not g.authorize("GET", "https://alvo.com/%2e%2e/admin").allowed
    assert g.authorize("GET", "https://alvo.com/administrator").allowed  # prefixo != caminho


def test_scope_total_cap_profile_and_window():
    g = ScopeGuard(cfg(max_total_requests=2))
    assert g.authorize("GET", "https://alvo.com/").allowed
    assert g.authorize("GET", "https://alvo.com/").allowed
    assert not g.authorize("GET", "https://alvo.com/").allowed
    assert not ScopeGuard(cfg()).authorize("GET", "https://alvo.com/", Profile.INTRUSIVE).allowed
    assert not ScopeGuard(cfg(window_end=utcnow() - timedelta(hours=1))).window_ok().allowed


def test_grade_matrix_reaches_every_grade():
    assert grade_for(Status.FAIL, Severity.HIGH) is Grade.BLUNDER
    assert grade_for(Status.FAIL, Severity.MEDIUM) is Grade.MISTAKE
    assert grade_for(Status.WARNING, Severity.MEDIUM) is Grade.INACCURACY
    assert grade_for(Status.PASS, Severity.LOW) is Grade.GOOD
    assert grade_for(Status.PASS, Severity.HIGH) is Grade.BEST
    assert grade_for(Status.PASS, Severity.MEDIUM, exemplary=True) is Grade.GREAT
    assert grade_for(Status.PASS, Severity.HIGH, exemplary=True) is Grade.BRILLIANT
    assert grade_for(Status.INCONCLUSIVE, Severity.HIGH) is Grade.INCONCLUSIVE


def _mv(status, sev, grade) -> Move:
    return Move(move=1, test_id="X", title="x", phase=Phase.OPENING, profile=Profile.PASSIVE,
                status=status, severity=sev, grade=grade)


def test_score_weights_and_ignores_inconclusive():
    perfect = compute_score([_mv(Status.PASS, Severity.HIGH, Grade.BEST)])
    assert perfect.accuracy == 100 and perfect.eval_bar == 100
    mixed = compute_score([_mv(Status.FAIL, Severity.HIGH, Grade.BLUNDER),
                           _mv(Status.PASS, Severity.LOW, Grade.GOOD),
                           _mv(Status.INCONCLUSIVE, Severity.HIGH, Grade.INCONCLUSIVE)])
    assert mixed.accuracy == round((3 * 0 + 1 * 95) / 4, 1)
    assert compute_score([]).accuracy == 0


def test_tls_error_becomes_result_not_crash():
    exc = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate")
    assert classify_error(exc) == "tls"
    assert classify_error(httpx.ConnectTimeout("x")) == "timeout"

    async def go():
        sink, config = MemorySink(), cfg()
        f = Fetcher("c1", config, sink, ScopeGuard(config))

        async def boom(*a, **k):
            raise exc

        f.client.request = boom
        res = await f.request("GET", "https://alvo.com/", profile=Profile.PASSIVE, ev_id="e1")
        await f.aclose()
        return res, sink

    res, sink = asyncio.run(go())
    assert res.error == "tls" and not res.ok
    assert sink.audits and sink.audits[0].reason == "falha: tls"


def test_out_of_scope_is_blocked_and_audited():
    async def go():
        sink, config = MemorySink(), cfg()
        f = Fetcher("c1", config, sink, ScopeGuard(config))
        res = await f.request("GET", "https://evil.com/?token=abc", profile=Profile.PASSIVE, ev_id="e1")
        await f.aclose()
        return res, sink

    res, sink = asyncio.run(go())
    assert res.error == "blocked"
    assert sink.audits[0].allowed is False and "token" not in sink.audits[0].url
    assert any(e.type is EventType.SCOPE_BLOCKED for e in sink.events)

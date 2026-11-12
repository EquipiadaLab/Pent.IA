"""Campanha completa do Motor contra o alvo de ensaio local."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "devtools"))
import lab_server  # noqa: E402

from app.engine.memory_sink import MemorySink  # noqa: E402
from app.engine.runner import run_campaign  # noqa: E402
from app.engine.scope import utcnow  # noqa: E402
from app.models import Approval, CampaignConfig, CampaignState, EventType, Grade  # noqa: E402


@pytest.fixture
def vulnerable():
    srv, url = lab_server.start(hardened=False)
    yield url
    srv.shutdown()


@pytest.fixture
def hardened():
    srv, url = lab_server.start(hardened=True)
    yield url
    srv.shutdown()


def run(url: str, sink: MemorySink, **kw):
    config = CampaignConfig(origin=url, authorized_by="Org", authorized_at=utcnow(),
                            max_requests_per_second=200, **kw)
    return asyncio.run(run_campaign("c1", config, sink))


def by_id(campaign):
    return {m.test_id: m for m in campaign.moves}


def test_vulnerable_target_findings(vulnerable):
    sink = MemorySink(approve=True)
    c = run(vulnerable, sink)
    m = by_id(c)
    assert c.state is CampaignState.FINISHED
    assert m["TLS-001"].grade is Grade.BLUNDER       # alvo em HTTP
    assert m["REDIR-001"].grade is Grade.MISTAKE      # nao redireciona
    assert m["CORS-001"].grade is Grade.BLUNDER       # reflete origem + credenciais
    assert m["CSP-001"].grade is Grade.MISTAKE        # so Report-Only
    assert m["COOKIE-001"].grade is Grade.MISTAKE     # sessao sem flags
    assert m["METHOD-001"].grade is Grade.MISTAKE     # TRACE habilitado
    assert m["FILE-001"].grade is Grade.BLUNDER and m["FILE-002"].grade is Grade.BLUNDER
    assert m["ERR-001"].grade is Grade.MISTAKE
    assert m["HSTS-001"].grade is Grade.INCONCLUSIVE  # n/a em HTTP
    assert c.score.accuracy < 40


def test_hardened_target_scores_high(hardened):
    c = run(hardened, MemorySink(approve=True))
    m = by_id(c)
    assert m["CSP-001"].grade is Grade.GREAT
    assert m["CLICK-001"].grade is Grade.GREAT
    assert m["FILE-001"].grade is Grade.BEST
    assert c.score.accuracy > 80


def test_denied_approval_is_not_executed_and_not_scored(vulnerable):
    sink = MemorySink(approve=False)
    c = run(vulnerable, sink)
    for tid in ("FILE-001", "FILE-002", "ERR-001"):
        mv = by_id(c)[tid]
        assert mv.approval is Approval.DENIED and mv.status is None and mv.grade is None
    paths = [a.url for a in sink.audits]
    assert not any(p.endswith("/.git/HEAD") or p.endswith("/.env") for p in paths)


def test_stop_preserves_partial_results(vulnerable):
    sink = MemorySink(approve=True, stop_after_events=12)
    c = run(vulnerable, sink)
    assert c.state is CampaignState.STOPPED
    assert 0 < len(c.moves) < 14
    assert sink.events[-1].type is EventType.CAMPAIGN_FINISHED


def test_events_are_live_and_in_order(vulnerable):
    sink = MemorySink(approve=True)
    run(vulnerable, sink)
    types = [e.type for e in sink.events]
    assert types[0] is EventType.CAMPAIGN_STARTED and types[-1] is EventType.CAMPAIGN_FINISHED
    assert EventType.APPROVAL_REQUESTED in types and EventType.SCORE_UPDATED in types
    assert [e.seq for e in sink.events] == sorted(e.seq for e in sink.events)


def test_no_secrets_in_events_or_audit(vulnerable):
    sink = MemorySink(approve=True)
    c = run(vulnerable, sink)
    blob = json.dumps([e.model_dump(mode="json") for e in sink.events]
                      + [a.model_dump(mode="json") for a in sink.audits]
                      + [m.model_dump(mode="json") for m in c.moves])
    for secret in ("abc123SESSION", "hunter2", "s3cr3t"):
        assert secret not in blob


def test_only_get_and_options_were_sent(vulnerable):
    sink = MemorySink(approve=True)
    run(vulnerable, sink)
    assert {a.method for a in sink.audits} <= {"GET", "OPTIONS"}


def test_window_in_the_past_refuses_to_run(vulnerable):
    from datetime import timedelta
    c = run(vulnerable, MemorySink(), window_end=utcnow() - timedelta(hours=1))
    assert c.state is CampaignState.FAILED and not c.moves

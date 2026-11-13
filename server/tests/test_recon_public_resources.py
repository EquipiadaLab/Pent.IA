"""Checks passivos de Recon contra um alvo HTTP temporario e local."""

from __future__ import annotations

import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.engine.memory_sink import MemorySink
from app.engine.runner import run_campaign
from app.engine.scope import utcnow
from app.models import CampaignConfig, Status


@pytest.fixture
def public_site():
    responses = {
        "/robots.txt": (200, "text/plain", "User-agent: *\nDisallow: /private\n"),
        "/sitemap.xml": (200, "application/xml", "<urlset><url><loc>/</loc></url></urlset>"),
        "/openapi.json": (200, "application/json", '{"openapi":"3.0.0","paths":{}}'),
    }

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            status, content_type, body = responses.get(
                self.path.split("?", 1)[0], (404, "text/plain", "not found")
            )
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _run_one(origin: str, test_id: str):
    config = CampaignConfig(
        origin=origin,
        authorized_by="teste-local",
        authorized_at=utcnow(),
        only_tests=[test_id],
        max_requests_per_second=100,
    )
    sink = MemorySink(approve=True)
    campaign = asyncio.run(run_campaign(f"recon-{test_id}", config, sink))
    assert len(campaign.moves) == 1
    return campaign.moves[0], sink


@pytest.mark.parametrize(
    ("test_id", "expected_path"),
    [
        ("RECON-ROBOTS-001", "/robots.txt"),
        ("RECON-SITEMAP-001", "/sitemap.xml"),
        ("RECON-OPENAPI-001", "/openapi.json"),
    ],
)
def test_public_resources_are_observed_not_reported_as_vulnerabilities(
    public_site, test_id: str, expected_path: str
):
    move, sink = _run_one(public_site, test_id)

    assert move.status is Status.PASS
    assert move.recommended_by == "Recon"
    assert move.attack_tactic_id == "TA0043"
    assert move.attack_technique_id == "T1594"
    assert move.evidence and expected_path in move.evidence[0].request
    assert len(sink.audits) == 1
    assert sink.audits[0].method == "GET"
    assert sink.audits[0].url.endswith(expected_path)


def test_absent_security_txt_is_a_low_priority_actionable_warning(public_site):
    move, sink = _run_one(public_site, "RECON-SECURITYTXT-001")

    assert move.status is Status.WARNING
    assert move.recommended_by == "Recon"
    assert move.recommendation and "security.txt" in move.recommendation
    assert move.evidence and "/.well-known/security.txt" in move.evidence[0].request
    # Alertas sao reconfirmados pelo Motor com uma segunda observacao.
    assert len(sink.audits) == 2
    assert all(a.method == "GET" for a in sink.audits)

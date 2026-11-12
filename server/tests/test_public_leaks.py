"""Testes de nao-vazamento: o que sai para o front nunca contem segredo."""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app import models as m
from app.public_schemas import (
    ApprovalDecisionRequest,
    CreateCampaignRequest,
    PublicCampaign,
    PublicEvent,
    PublicGameReview,
)
from app.redact import mask_set_cookie, sanitize_headers, sanitize_url, scrub_text

NOW = datetime(2026, 11, 12, 14, 0, tzinfo=UTC)
SECRETS = ["abc123SESSION", "AKIAABCDEFGHIJKLMNOP", "s3cr3tTOKEN", "hunter2", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sigsigsig"]


def _config() -> m.CampaignConfig:
    return m.CampaignConfig(
        origin="https://user:hunter2@alvo.com:443/?token=s3cr3tTOKEN",
        authorized_by="Organizacao",
        authorized_at=NOW,
    )


def _move() -> m.Move:
    return m.Move(
        move=1,
        test_id="COOKIE-001",
        title="Cookies",
        phase=m.Phase.MIDDLEGAME,
        profile=m.Profile.PASSIVE,
        status=m.Status.WARNING,
        grade=m.Grade.INACCURACY,
        evidence=[
            m.Evidence(
                id="ev1",
                request="GET /?token=s3cr3tTOKEN HTTP/1.1",
                response_status=200,
                response_headers={
                    "Set-Cookie": "sid=abc123SESSION; HttpOnly; Secure",
                    "Authorization": "Bearer abc123SESSION",
                    "X-Internal-Debug": "AKIAABCDEFGHIJKLMNOP",
                    "Strict-Transport-Security": "max-age=31536000",
                    "Location": "https://alvo.com/login?next=/&token=s3cr3tTOKEN",
                },
                note="password=hunter2 encontrado na pagina",
            )
        ],
        explanation="Token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sigsigsig vazou",
    )


def _dump(obj) -> str:
    return json.dumps(obj.model_dump(mode="json"))


def test_campaign_has_no_secrets():
    c = m.Campaign(id="c1", config=_config(), created_at=NOW, moves=[_move()])
    out = _dump(PublicCampaign.from_internal(c))
    for s in SECRETS:
        assert s not in out, f"vazou: {s}"
    assert "x-internal-debug" not in out and "authorization" not in out


def test_report_and_event_have_no_secrets():
    mv = _move()
    c = m.Campaign(id="c1", config=_config(), created_at=NOW, moves=[mv])
    rep = m.GameReview(
        campaign=c,
        executive_summary="api_key=s3cr3tTOKEN no resumo",
        audit=[
            m.AuditEntry(
                campaign_id="c1", at=NOW, method="GET",
                url="https://alvo.com/x?token=s3cr3tTOKEN", allowed=True,
            )
        ],
    )
    out = _dump(PublicGameReview.from_internal(rep))
    ev = m.Event(
        campaign_id="c1", type=m.EventType.FINDING_CREATED, at=NOW, move=mv,
        data={"internal": {"password": "hunter2"}, "note": "token=s3cr3tTOKEN"},
    )
    out += _dump(PublicEvent.from_internal(ev))
    for s in SECRETS:
        assert s not in out, f"vazou: {s}"


def test_cookie_keeps_flags_hides_value():
    assert mask_set_cookie("sid=abc; HttpOnly; Secure") == "sid=***; HttpOnly; Secure"


def test_header_allowlist_and_url_sanitize():
    h = sanitize_headers({"Set-Cookie": "a=b", "X-Secret": "x", "X-Frame-Options": "DENY"})
    assert set(h) == {"set-cookie", "x-frame-options"}
    assert sanitize_url("https://u:p@a.com:8443/p?q=1#f") == "https://a.com:8443/p"


def test_scrub_text_limits_size():
    assert len(scrub_text("a" * 100_000)) == 4000


def test_public_models_reject_unknown_fields():
    with pytest.raises(ValidationError):
        PublicCampaign.model_validate({"id": "x", "extra_field": 1})


def test_requests_cannot_set_methods_or_unknown_fields():
    with pytest.raises(ValidationError):
        CreateCampaignRequest(origin="https://a.com", authorized_by="x", allowed_methods=["POST"])
    with pytest.raises(ValidationError):
        CreateCampaignRequest(origin="https://a.com", authorized_by="x", max_requests_per_second=100)
    with pytest.raises(ValidationError):
        ApprovalDecisionRequest(decision="approved", is_admin=True)

"""Garante que o contrato do dossie (p.16) valida no models.py."""

from app.models import Approval, Grade, Move, Status

SAMPLE = {
    "move": 3,
    "test_id": "COOKIE-001",
    "title": "Flags de cookies",
    "phase": "middlegame",
    "profile": "passive",
    "wstg": "WSTG-SESS-02",
    "owasp_top10": "A07:2025",
    "status": "warning",
    "severity": "medium",
    "grade": "inaccuracy",
    "confidence": "high",
    "evidence": [
        {
            "id": "ev-3-1",
            "request": "GET / HTTP/1.1",
            "response_headers": {"set-cookie": "sid=***; HttpOnly"},
        }
    ],
    "started_at": "2026-11-12T14:03:11Z",
    "finished_at": "2026-11-12T14:03:12Z",
}


def test_sample_move_validates():
    m = Move.model_validate(SAMPLE)
    assert m.status is Status.WARNING
    assert m.grade is Grade.INACCURACY
    assert m.approval is Approval.NOT_REQUIRED


def test_pending_move_has_no_result():
    m = Move.model_validate(
        {
            "move": 9,
            "test_id": "CONF-004",
            "title": "Arquivo /.git/HEAD exposto",
            "phase": "endgame",
            "profile": "active_light",
            "approval": "pending",
        }
    )
    assert m.status is None and m.grade is None

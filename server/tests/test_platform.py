"""Testes do Trilho B (Plataforma) com o run_campaign de exemplo.

Exercita a entrega ao Motor: EventSink (emit/audit), fila de aprovacao
(wait_approval) e parada (should_stop), alem do mascaramento de segredos e
do Game Review.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from app import sample_runner
from app.audit import mask_cookie_value, mask_headers, mask_text
from app.db import Database
from app.models import (
    Approval,
    Campaign,
    CampaignConfig,
    CampaignState,
    Evidence,
    GameReview,
    Grade,
    Move,
    Phase,
    Profile,
    Severity,
    Status,
    Verdict,
)
from app.reporter import ReportBuilder, TemplateLLMClient
from app.report import PDF_AVAILABLE, to_markdown, to_pdf
from app.sink import ApprovalNotPending, Coordinator


def _config() -> CampaignConfig:
    return CampaignConfig(
        origin="https://alvo.exemplo",
        authorized_by="Sidney",
        authorized_at=datetime.now(timezone.utc),
    )


async def _create(db: Database, cid: str) -> None:
    """Replica o que o POST /campaigns faz antes de lancar o runner."""
    await db.create_campaign(
        Campaign(id=cid, config=_config(), created_at=datetime.now(timezone.utc))
    )


async def _wait_for(predicate, timeout: float = 2.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condicao nao satisfeita dentro do timeout")


@pytest.mark.asyncio
async def test_campanha_completa_com_aprovacao() -> None:
    db = Database(":memory:")
    co = Coordinator(db)
    cid = "camp-1"
    await _create(db, cid)
    sink = co.new_sink(cid)

    task = asyncio.create_task(sample_runner.run_campaign(cid, _config(), sink))

    # O fake joga 3 lances e para aguardando aprovacao do lance 4 (endgame).
    await _wait_for(lambda: 4 in co.pending_moves(cid))
    assert await db.get_state(cid) is CampaignState.WAITING_APPROVAL

    decision = await co.resolve_approval(cid, 4, approved=True, actor="Sidney")
    assert decision is Approval.APPROVED

    campaign = await task
    assert campaign.state is CampaignState.FINISHED
    assert await db.get_state(cid) is CampaignState.FINISHED

    moves = await db.list_moves(cid)
    assert [m.move for m in moves] == [1, 2, 3, 4]
    move4 = await db.get_move(cid, 4)
    assert move4.approval is Approval.APPROVED
    assert move4.grade is Grade.BLUNDER

    # Segredo do cookie no lance 3 nao pode vazar na evidencia persistida.
    move3 = await db.get_move(cid, 3)
    assert "segredo-super-secreto" not in move3.evidence[0].response_headers["set-cookie"]
    assert "sid=***" in move3.evidence[0].response_headers["set-cookie"]

    events = await db.list_events(cid)
    assert events[0].seq == 1  # seq monotonico atribuido pela plataforma
    assert [e.seq for e in events] == list(range(1, len(events) + 1))

    audit = await db.list_audit(cid)
    assert len(audit) >= 3
    assert all(a.campaign_id == cid for a in audit)

    db.close()


@pytest.mark.asyncio
async def test_parada_nega_aprovacao() -> None:
    db = Database(":memory:")
    co = Coordinator(db)
    cid = "camp-2"
    await _create(db, cid)
    sink = co.new_sink(cid)

    task = asyncio.create_task(sample_runner.run_campaign(cid, _config(), sink))
    await _wait_for(lambda: 4 in co.pending_moves(cid))

    await co.request_stop(cid, actor="Sidney")
    campaign = await task

    assert await db.get_state(cid) is CampaignState.STOPPED
    move4 = await db.get_move(cid, 4)
    assert move4.approval is Approval.DENIED
    assert campaign.finished_at is not None
    db.close()


@pytest.mark.asyncio
async def test_resolver_aprovacao_inexistente_falha() -> None:
    db = Database(":memory:")
    co = Coordinator(db)
    with pytest.raises(ApprovalNotPending):
        await co.resolve_approval("camp-x", 9, approved=True, actor="Sidney")
    db.close()


@pytest.mark.asyncio
async def test_game_review_markdown() -> None:
    db = Database(":memory:")
    co = Coordinator(db)
    cid = "camp-3"
    await _create(db, cid)
    sink = co.new_sink(cid)
    task = asyncio.create_task(sample_runner.run_campaign(cid, _config(), sink))
    await _wait_for(lambda: 4 in co.pending_moves(cid))
    await co.resolve_approval(cid, 4, approved=True, actor="Sidney")
    await task

    campaign = await db.get_campaign(cid)
    audit = await co.audit.history(cid)
    review = await ReportBuilder(TemplateLLMClient()).build(campaign, audit)
    md = to_markdown(review)

    assert "# Game Review" in md
    assert "Momentos-chave" in md
    assert "segredo-super-secreto" not in md  # segredos nunca no relatorio
    db.close()


def test_mascaramento_unitario() -> None:
    assert mask_cookie_value("sid=abc123; HttpOnly; Secure") == "sid=***; HttpOnly; Secure"
    headers = mask_headers({"Authorization": "Bearer xyz", "Server": "nginx"})
    assert headers["Authorization"] == "***"
    assert headers["Server"] == "nginx"
    assert "token123" not in (mask_text("api_key=token123") or "")


def test_detailed_report_shows_evidence_impact_and_remediation() -> None:
    """O PDF/Markdown deve explicar o achado, sem virar guia de exploracao."""
    finding = Move(
        move=1,
        test_id="REDIR-001",
        title="Redirecionamento HTTP para HTTPS",
        phase=Phase.OPENING,
        profile=Profile.PASSIVE,
        status=Status.FAIL,
        severity=Severity.MEDIUM,
        grade=Grade.MISTAKE,
        approval=Approval.APPROVED,
        verdict=Verdict.CONFIRMED,
        recommended_by="Recon",
        attack_tactic_id="TA0043",
        attack_tactic_name="Reconnaissance",
        attack_technique_id="T1595",
        attack_technique_name="Active Scanning",
        attack_url="https://attack.mitre.org/techniques/T1595",
        explanation="A origem HTTP respondeu sem redirecionar para HTTPS.",
        impact="Uma conexao HTTP pode ser observada ou alterada em uma rede comprometida.",
        exploitation_scenario="Um invasor em uma rede insegura pode tentar interferir no trafego HTTP antes da protecao HTTPS.",
        recommendation="Redirecionar HTTP para HTTPS com status 301 e habilitar HSTS.",
        evidence=[Evidence(id="ev-1-1", request="GET / HTTP/1.1", response_status=200)],
    )
    campaign = Campaign(
        id="report-detail",
        config=_config(),
        state=CampaignState.FINISHED,
        created_at=datetime.now(timezone.utc),
        moves=[finding],
    )
    review = GameReview(campaign=campaign, executive_summary="Um risco de transporte foi confirmado.")

    markdown = to_markdown(review)
    for text in (
        "Achados prioritarios e recomendacoes",
        "O que foi encontrado",
        "Evidencia observada",
        "Como esta configuracao pode ser aproveitada",
        "Melhor jogada: como corrigir",
        "Confirmado em segunda observacao independente",
        "TA0043",
        "Redirecionar HTTP para HTTPS",
    ):
        assert text in markdown

    if PDF_AVAILABLE:
        assert to_pdf(review).startswith(b"%PDF")

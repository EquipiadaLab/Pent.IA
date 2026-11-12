"""Exportacao do Game Review (Trilho B): Markdown e PDF.

- Markdown sempre disponivel (stdlib).
- PDF e best-effort via ``reportlab``; se a lib nao estiver instalada, a
  API responde 501 e o Markdown continua funcionando.
"""

from __future__ import annotations

from app.models import GameReview, Move

PDF_AVAILABLE: bool
try:  # reportlab e opcional
    from reportlab.lib.pagesizes import A4  # noqa: F401
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    PDF_AVAILABLE = True
except Exception:  # pragma: no cover - ausencia e caminho valido
    PDF_AVAILABLE = False


def _move_row(m: Move) -> str:
    grade = m.grade.value if m.grade else "-"
    status = m.status.value if m.status else "pendente"
    ev = ", ".join(e.id for e in m.evidence) or "-"
    return (
        f"| {m.move} | {m.title} | {m.phase.value} | {status} | {grade} |"
        f" {m.severity.value} | {m.approval.value} | {ev} |"
    )


def to_markdown(review: GameReview) -> str:
    c = review.campaign
    lines: list[str] = []
    lines.append(f"# Game Review — {c.config.origin}")
    lines.append("")
    lines.append(f"- **Campanha:** `{c.id}`")
    lines.append(f"- **Estado:** {c.state.value}")
    lines.append(f"- **Autorizado por:** {c.config.authorized_by}")
    lines.append(f"- **Criada em:** {c.created_at.isoformat()}")
    if c.finished_at:
        lines.append(f"- **Encerrada em:** {c.finished_at.isoformat()}")
    if c.score:
        lines.append(
            f"- **Accuracy:** {c.score.accuracy:.1f} | **Eval bar:** {c.score.eval_bar:+.1f}"
        )
    lines.append("")

    lines.append("## Resumo executivo")
    lines.append("")
    lines.append(review.executive_summary or "_(sem resumo)_")
    lines.append("")

    if review.key_moments:
        lines.append("## Momentos-chave")
        lines.append("")
        for km in review.key_moments:
            lines.append(f"- **Lance {km.move}:** {km.summary}")
        lines.append("")

    lines.append("## Lances")
    lines.append("")
    lines.append("| # | Titulo | Fase | Status | Grade | Severidade | Aprovacao | Evidencias |")
    lines.append("|---|--------|------|--------|-------|------------|-----------|------------|")
    for m in c.moves:
        lines.append(_move_row(m))
    lines.append("")

    lines.append("## Trilha de auditoria")
    lines.append("")
    if review.audit:
        lines.append("| Quando | Metodo | URL | Permitido | Motivo | HTTP |")
        lines.append("|--------|--------|-----|-----------|--------|------|")
        for a in review.audit:
            lines.append(
                f"| {a.at.isoformat()} | {a.method} | {a.url} |"
                f" {'sim' if a.allowed else 'nao'} | {a.reason or '-'} |"
                f" {a.status_code if a.status_code is not None else '-'} |"
            )
    else:
        lines.append("_(sem registros)_")
    lines.append("")
    return "\n".join(lines)


def to_pdf(review: GameReview) -> bytes:
    """Renderiza o Game Review em PDF. Requer ``reportlab``."""
    if not PDF_AVAILABLE:  # pragma: no cover
        raise RuntimeError(
            "Exportacao PDF indisponivel: instale 'reportlab' (pip install reportlab)."
        )

    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Game Review")
    styles = getSampleStyleSheet()
    flow = []
    c = review.campaign

    flow.append(Paragraph(f"Game Review — {_esc(c.config.origin)}", styles["Title"]))
    flow.append(Spacer(1, 6 * mm))
    flow.append(Paragraph(f"Campanha: {c.id}", styles["Normal"]))
    flow.append(Paragraph(f"Estado: {c.state.value}", styles["Normal"]))
    flow.append(Paragraph(f"Autorizado por: {_esc(c.config.authorized_by)}", styles["Normal"]))
    if c.score:
        flow.append(
            Paragraph(
                f"Accuracy: {c.score.accuracy:.1f} | Eval bar: {c.score.eval_bar:+.1f}",
                styles["Normal"],
            )
        )
    flow.append(Spacer(1, 6 * mm))

    flow.append(Paragraph("Resumo executivo", styles["Heading2"]))
    flow.append(Paragraph(_esc(review.executive_summary or "(sem resumo)"), styles["Normal"]))
    flow.append(Spacer(1, 4 * mm))

    if review.key_moments:
        flow.append(Paragraph("Momentos-chave", styles["Heading2"]))
        for km in review.key_moments:
            flow.append(Paragraph(f"Lance {km.move}: {_esc(km.summary)}", styles["Normal"]))
        flow.append(Spacer(1, 4 * mm))

    flow.append(Paragraph("Lances", styles["Heading2"]))
    for m in c.moves:
        grade = m.grade.value if m.grade else "-"
        status = m.status.value if m.status else "pendente"
        flow.append(
            Paragraph(
                f"{m.move}. {_esc(m.title)} — {m.phase.value} / {status} /"
                f" {grade} / {m.severity.value}",
                styles["Normal"],
            )
        )

    doc.build(flow)
    return buffer.getvalue()


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )

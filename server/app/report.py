"""Exportacao detalhada do Game Review em Markdown e PDF.

O relatorio usa apenas dados ja registrados pelo Motor e mascarados pela
Plataforma. Ele nao cria achados nem conclui que uma falha e exploravel sem
resultado/evidencia. Cenários de exploracao sao explicativos e defensivos:
descrevem impacto em alto nivel, sem payloads ou instrucoes ofensivas.
"""

from __future__ import annotations

from app.cve.models import CveMatch
from app.models import GameReview, Move, Status, Verdict

PDF_AVAILABLE: bool
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

    PDF_AVAILABLE = True
except Exception:  # pragma: no cover - ausencia e caminho valido
    PDF_AVAILABLE = False


def _move_row(m: Move) -> str:
    grade = m.grade.value if m.grade else "-"
    status = m.status.value if m.status else "pendente"
    ev = ", ".join(e.id for e in m.evidence) or "-"
    agent = m.recommended_by or "catalogo"
    return (
        f"| {m.move} | {m.title} | {agent} | {m.phase.value} | {status} | {grade} |"
        f" {m.severity.value} | {m.approval.value} | {ev} |"
    )


def _is_reportable_finding(m: Move) -> bool:
    """So mostra como risco aquilo que teve resultado e nao foi descartado."""
    return m.status in (Status.FAIL, Status.WARNING) and m.verdict is not Verdict.DISCARDED


def _confirmation(m: Move) -> str:
    if m.verdict is Verdict.CONFIRMED:
        return "Confirmado em segunda observacao independente."
    if m.verdict is Verdict.INCONCLUSIVE:
        return "Resultado inicial encontrado, mas a confirmacao foi inconclusiva."
    if m.verdict is Verdict.DISCARDED:
        return "Descartado: nao se reproduziu na segunda observacao."
    return "Nao exige confirmacao adicional."


def _scenario(m: Move) -> str:
    return m.exploitation_scenario or m.impact or "Impacto nao determinado por este teste."


def _mitre(m: Move) -> str:
    if not m.attack_tactic_id and not m.attack_technique_id:
        return "Nao associado a um agente MITRE nesta versao."
    tactic = " ".join(x for x in (m.attack_tactic_id, m.attack_tactic_name) if x)
    technique = " ".join(x for x in (m.attack_technique_id, m.attack_technique_name) if x)
    text = f"Tatica: {tactic or '-'} | Tecnica: {technique or '-'}"
    return text + (f" | Referencia: {m.attack_url}" if m.attack_url else "")


def _evidence_markdown(m: Move) -> list[str]:
    if not m.evidence:
        return ["- Nenhuma evidencia de resposta foi registrada."]
    lines: list[str] = []
    for ev in m.evidence:
        status = str(ev.response_status) if ev.response_status is not None else "sem status HTTP"
        note = f" — {ev.note}" if ev.note else ""
        lines.append(f"- `{ev.id}`: `{ev.request}` → {status}{note}")
    return lines


def _finding_markdown(m: Move) -> list[str]:
    grade = m.grade.value if m.grade else "-"
    lines = [
        f"### Lance {m.move} — {m.title}",
        "",
        f"- **Classificacao:** {m.status.value if m.status else 'pendente'} / {grade} / {m.severity.value}",
        f"- **Agente que recomendou:** {m.recommended_by or 'catalogo de regras'}",
        f"- **MITRE ATT&CK:** {_mitre(m)}",
        f"- **WSTG / OWASP:** {m.wstg or '-'} / {m.owasp_top10 or '-'}",
        "",
        "**O que foi encontrado**",
        m.explanation or "Sem explicacao registrada.",
        "",
        "**Evidencia observada**",
        *_evidence_markdown(m),
        "",
        "**Como esta configuracao pode ser aproveitada**",
        _scenario(m),
        "",
        "**Melhor jogada: como corrigir**",
        m.recommendation or "Nenhuma correcao foi sugerida para este resultado.",
        "",
        "**Confirmacao**",
        _confirmation(m),
    ]
    if m.ai_explanation:
        lines.extend(["", "**Comentario revisado pela IA**", m.ai_explanation])
    lines.append("")
    return lines


def _cve_markdown(matches: list[CveMatch]) -> list[str]:
    lines = ["## CVEs e exploits conhecidos (NVD)", ""]
    with_results = [m for m in matches if m.cves]
    if not matches:
        lines.append(
            "_Nenhuma tecnologia com versao identificavel foi observada nesta campanha; "
            "nenhuma correlacao de CVE foi realizada._"
        )
        lines.append("")
        return lines
    if not with_results:
        lines.append(
            "_Tecnologias observadas foram consultadas na NVD, mas nenhum CVE publico foi encontrado "
            "para os termos abaixo:_ " + ", ".join(f"`{m.search_term}`" for m in matches)
        )
        lines.append("")
        return lines
    for match in with_results:
        origem = f" (lance {match.move})" if match.move else ""
        lines.append(f"### Tecnologia observada: `{match.search_term}`{origem}")
        lines.append("")
        for cve in match.cves:
            severity = f"{cve.cvss_severity} ({cve.cvss_score})" if cve.cvss_severity else "sem score CVSS"
            lines.append(f"- **[{cve.cve_id}]({cve.nvd_url})** — {severity}")
            lines.append(f"  {cve.description}")
            if cve.cwe_ids:
                lines.append(f"  CWE: {', '.join(cve.cwe_ids)}")
            if cve.exploits:
                for exp in cve.exploits:
                    lines.append(f"  ⚠️ Exploit público conhecido: {exp.url}")
        lines.append("")
    for match in matches:
        if match.error:
            lines.append(f"_Consulta à NVD para `{match.search_term}` falhou ({match.error}); tente novamente mais tarde._")
            lines.append("")
    return lines


def to_markdown(review: GameReview, cves: list[CveMatch] | None = None) -> str:
    c = review.campaign
    lines: list[str] = [f"# Game Review — {c.config.origin}", ""]
    lines.extend(
        [
            f"- **Campanha:** `{c.id}`",
            f"- **Estado:** {c.state.value}",
            f"- **Autorizado por:** {c.config.authorized_by}",
            f"- **Criada em:** {c.created_at.isoformat()}",
        ]
    )
    if c.finished_at:
        lines.append(f"- **Encerrada em:** {c.finished_at.isoformat()}")
    if c.score:
        lines.append(f"- **Accuracy:** {c.score.accuracy:.1f} | **Eval bar:** {c.score.eval_bar:+.1f}")
    lines.extend(["", "## Resumo executivo", "", review.executive_summary or "_(sem resumo)_", ""])

    if cves is not None:
        lines.extend(_cve_markdown(cves))

    findings = [m for m in c.moves if _is_reportable_finding(m)]
    lines.extend(["## Achados prioritarios e recomendacoes", ""])
    if findings:
        for move in findings:
            lines.extend(_finding_markdown(move))
    else:
        lines.extend(["Nenhuma falha ou alerta confirmado foi registrado nesta campanha.", ""])

    if review.key_moments:
        lines.extend(["## Momentos-chave", ""])
        for km in review.key_moments:
            lines.append(f"- **Lance {km.move}:** {km.summary}")
        lines.append("")

    lines.extend(
        [
            "## Todos os lances",
            "",
            "| # | Titulo | Agente | Fase | Status | Grade | Severidade | Aprovacao | Evidencias |",
            "|---|--------|--------|-------|--------|-------|------------|-----------|------------|",
        ]
    )
    lines.extend(_move_row(m) for m in c.moves)
    lines.append("")

    lines.extend(["## Trilha de auditoria", ""])
    if review.audit:
        lines.extend(["| Quando | Metodo | URL | Permitido | Motivo | HTTP |", "|--------|--------|-----|-----------|--------|------|"])
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


def _paragraph(text: str, style) -> Paragraph:
    """Texto puro escapado; novas linhas simples viram quebra visual no PDF."""
    return Paragraph(_esc(text).replace("\n", "<br/>"), style)


def _add_finding_pdf(flow: list, m: Move, styles) -> None:
    grade = m.grade.value if m.grade else "-"
    flow.append(_paragraph(f"Lance {m.move} — {m.title}", styles["Heading2"]))
    flow.append(_paragraph(
        f"Classificacao: {m.status.value if m.status else 'pendente'} / {grade} / {m.severity.value}",
        styles["Normal"],
    ))
    flow.append(_paragraph(f"Agente que recomendou: {m.recommended_by or 'catalogo de regras'}", styles["Normal"]))
    flow.append(_paragraph(f"MITRE ATT&CK: {_mitre(m)}", styles["Normal"]))
    flow.append(_paragraph(f"WSTG / OWASP: {m.wstg or '-'} / {m.owasp_top10 or '-'}", styles["Normal"]))
    flow.append(Spacer(1, 2 * mm))

    for label, body in (
        ("O que foi encontrado", m.explanation or "Sem explicacao registrada."),
        ("Como esta configuracao pode ser aproveitada", _scenario(m)),
        ("Melhor jogada: como corrigir", m.recommendation or "Nenhuma correcao foi sugerida."),
        ("Confirmacao", _confirmation(m)),
    ):
        flow.append(_paragraph(label, styles["Heading3"]))
        flow.append(_paragraph(body, styles["Normal"]))
        flow.append(Spacer(1, 1.5 * mm))

    flow.append(_paragraph("Evidencia observada", styles["Heading3"]))
    for line in _evidence_markdown(m):
        flow.append(_paragraph(line.removeprefix("- ").replace("`", ""), styles["Normal"]))
    flow.append(Spacer(1, 4 * mm))


def _add_cve_pdf(flow: list, matches: list[CveMatch], styles) -> None:
    flow.append(_paragraph("CVEs e exploits conhecidos (NVD)", styles["Heading1"]))
    with_results = [m for m in matches if m.cves]
    if not matches:
        flow.append(_paragraph(
            "Nenhuma tecnologia com versao identificavel foi observada nesta campanha; "
            "nenhuma correlacao de CVE foi realizada.", styles["Normal"],
        ))
        flow.append(Spacer(1, 4 * mm))
        return
    if not with_results:
        terms = ", ".join(m.search_term for m in matches)
        flow.append(_paragraph(
            f"Tecnologias observadas foram consultadas na NVD, mas nenhum CVE publico foi "
            f"encontrado para: {terms}.", styles["Normal"],
        ))
        flow.append(Spacer(1, 4 * mm))
        return
    for match in with_results:
        origem = f" (lance {match.move})" if match.move else ""
        flow.append(_paragraph(f"Tecnologia observada: {match.search_term}{origem}", styles["Heading2"]))
        for cve in match.cves:
            severity = f"{cve.cvss_severity} ({cve.cvss_score})" if cve.cvss_severity else "sem score CVSS"
            flow.append(_paragraph(f"{cve.cve_id} — {severity}", styles["Heading3"]))
            flow.append(_paragraph(cve.description, styles["Normal"]))
            if cve.cwe_ids:
                flow.append(_paragraph(f"CWE: {', '.join(cve.cwe_ids)}", styles["Normal"]))
            for exp in cve.exploits:
                flow.append(_paragraph(f"Exploit publico conhecido: {exp.url}", styles["Normal"]))
            flow.append(_paragraph(f"Referencia: {cve.nvd_url}", styles["Normal"]))
            flow.append(Spacer(1, 2 * mm))
    flow.append(Spacer(1, 4 * mm))


def to_pdf(review: GameReview, cves: list[CveMatch] | None = None) -> bytes:
    """Renderiza o Game Review detalhado. Requer ``reportlab``."""
    if not PDF_AVAILABLE:  # pragma: no cover
        raise RuntimeError("Exportacao PDF indisponivel: instale 'reportlab'.")

    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="Pentest Chess — Game Review",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    styles = getSampleStyleSheet()
    flow: list = []
    c = review.campaign

    flow.append(_paragraph(f"Game Review — {c.config.origin}", styles["Title"]))
    flow.append(_paragraph(f"Campanha: {c.id}", styles["Normal"]))
    flow.append(_paragraph(f"Estado: {c.state.value}", styles["Normal"]))
    flow.append(_paragraph(f"Autorizado por: {c.config.authorized_by}", styles["Normal"]))
    if c.score:
        flow.append(_paragraph(f"Accuracy: {c.score.accuracy:.1f} | Eval bar: {c.score.eval_bar:+.1f}", styles["Normal"]))
    flow.append(Spacer(1, 5 * mm))

    flow.append(_paragraph("Resumo executivo", styles["Heading1"]))
    flow.append(_paragraph(review.executive_summary or "(sem resumo)", styles["Normal"]))
    flow.append(Spacer(1, 5 * mm))

    if cves is not None:
        _add_cve_pdf(flow, cves, styles)

    findings = [m for m in c.moves if _is_reportable_finding(m)]
    flow.append(_paragraph("Achados prioritarios e recomendacoes", styles["Heading1"]))
    if findings:
        for move in findings:
            _add_finding_pdf(flow, move, styles)
    else:
        flow.append(_paragraph("Nenhuma falha ou alerta confirmado foi registrado nesta campanha.", styles["Normal"]))

    flow.append(PageBreak())
    flow.append(_paragraph("Todos os lances", styles["Heading1"]))
    for m in c.moves:
        grade = m.grade.value if m.grade else "-"
        status = m.status.value if m.status else "pendente"
        flow.append(_paragraph(
            f"{m.move}. {m.title} — agente: {m.recommended_by or 'catalogo'}; "
            f"status: {status}; nota: {grade}; aprovacao: {m.approval.value}.",
            styles["Normal"],
        ))

    doc.build(flow)
    return buffer.getvalue()


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

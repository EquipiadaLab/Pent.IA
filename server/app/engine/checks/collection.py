"""Checks de coleta de dados ja expostos publicamente pela aplicacao (TA0009).

Cobre T1213 (Data from Information Repositories): dados de interesse
acessiveis sem autenticacao, atraves de rotas e endpoints de API publicados
pela propria aplicacao. Cada funcao faz APENAS requisicoes GET de leitura a
caminhos fixos; nenhuma delas tenta login, injecao, forja de token ou
qualquer acao que exija credenciais.

Pensado para alvos de treino (ex.: OWASP Juice Shop) que expõem, por padrao,
endpoints REST sem controle de acesso adequado. A existencia de dados na
resposta e o achado: nao e feita qualquer tentativa de alterar ou apagar
nada no servidor.
"""

from __future__ import annotations

import json

from app.engine.checks.base import CheckContext, CheckOutcome
from app.models import Confidence, Severity, Status


def _evidence(result, note: str):
    if result.evidence is not None:
        result.evidence.note = note
        return [result.evidence]
    return []


async def ftp_directory_listing(ctx: CheckContext) -> CheckOutcome:
    """Verifica se /ftp expoe listagem de arquivos sem autenticacao."""
    result = await ctx.get("/ftp")
    if not result.ok:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            f"Nao foi possivel consultar /ftp ({result.error}).",
            confidence=Confidence.LOW,
        )
    body = result.response.text[:5000]
    status = result.response.status_code
    looks_like_listing = status == 200 and (
        "Index of" in body or "<table" in body.lower() or ".md" in body or ".pdf" in body
    )
    if looks_like_listing:
        return CheckOutcome(
            Status.FAIL,
            "A rota /ftp expoe uma listagem de arquivos sem exigir autenticacao.",
            "Remover a listagem publica de diretorio e exigir autenticacao para acessar arquivos internos.",
            severity=Severity.MEDIUM,
            evidence=_evidence(result, "Listagem de arquivos observada em /ftp."),
        )
    return CheckOutcome(
        Status.PASS,
        "A rota /ftp nao expoe listagem de arquivos.",
        evidence=_evidence(result, "Sem listagem de diretorio em /ftp."),
    )


async def public_user_data(ctx: CheckContext) -> CheckOutcome:
    """Verifica se a API de usuarios responde dados sem exigir sessao autenticada."""
    result = await ctx.get("/api/Users/")
    if not result.ok:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            f"Nao foi possivel consultar /api/Users/ ({result.error}).",
            confidence=Confidence.LOW,
        )
    if result.response.status_code != 200:
        return CheckOutcome(
            Status.PASS,
            "A API de usuarios nao respondeu dados sem autenticacao.",
            evidence=_evidence(result, "/api/Users/ nao retornou 200 sem sessao."),
        )
    try:
        payload = json.loads(result.response.text[:20_000])
    except ValueError:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            "A resposta de /api/Users/ nao pode ser interpretada como JSON.",
            confidence=Confidence.LOW,
            evidence=_evidence(result, "Resposta nao-JSON em /api/Users/."),
        )
    records = payload.get("data") if isinstance(payload, dict) else None
    count = len(records) if isinstance(records, list) else 0
    if count > 0:
        return CheckOutcome(
            Status.FAIL,
            f"A API /api/Users/ retornou {count} registro(s) de usuario sem exigir autenticacao.",
            "Exigir autenticacao e autorizacao (dono do recurso ou papel administrativo) para listar usuarios.",
            severity=Severity.HIGH,
            evidence=_evidence(result, f"{count} registro(s) de usuario expostos sem sessao."),
        )
    return CheckOutcome(
        Status.PASS,
        "A API de usuarios respondeu 200, mas sem registros expostos.",
        confidence=Confidence.MEDIUM,
        evidence=_evidence(result, "Resposta 200 em /api/Users/ sem registros de dados."),
    )


async def public_feedback_data(ctx: CheckContext) -> CheckOutcome:
    """Verifica se a API de feedback expoe autor/e-mail de outros usuarios sem sessao."""
    result = await ctx.get("/api/Feedbacks/")
    if not result.ok:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            f"Nao foi possivel consultar /api/Feedbacks/ ({result.error}).",
            confidence=Confidence.LOW,
        )
    if result.response.status_code != 200:
        return CheckOutcome(
            Status.PASS,
            "A API de feedback nao respondeu dados sem autenticacao.",
            evidence=_evidence(result, "/api/Feedbacks/ nao retornou 200 sem sessao."),
        )
    try:
        payload = json.loads(result.response.text[:20_000])
    except ValueError:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            "A resposta de /api/Feedbacks/ nao pode ser interpretada como JSON.",
            confidence=Confidence.LOW,
            evidence=_evidence(result, "Resposta nao-JSON em /api/Feedbacks/."),
        )
    records = payload.get("data") if isinstance(payload, dict) else None
    identifiable = 0
    if isinstance(records, list):
        for item in records:
            if isinstance(item, dict) and (item.get("UserId") or item.get("author")):
                identifiable += 1
    if identifiable > 0:
        return CheckOutcome(
            Status.WARNING,
            f"A API /api/Feedbacks/ retornou {identifiable} registro(s) associados a um usuario, sem exigir autenticacao.",
            "Remover identificadores de usuario da resposta publica ou exigir autenticacao para consultar feedback.",
            severity=Severity.MEDIUM,
            evidence=_evidence(result, f"{identifiable} registro(s) de feedback com identificador de usuario."),
        )
    return CheckOutcome(
        Status.PASS,
        "A API de feedback respondeu 200 sem expor identificadores de usuario.",
        confidence=Confidence.MEDIUM,
        evidence=_evidence(result, "Resposta 200 em /api/Feedbacks/ sem identificador de usuario."),
    )

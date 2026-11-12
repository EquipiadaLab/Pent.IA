"""Ativo leve: CORS, metodos HTTP, arquivos expostos e pagina de erro.

Tudo e GET/OPTIONS. Corpo de resposta e lido so em memoria para classificar;
NUNCA vai para evidencia (poderia conter segredos de verdade).
"""

from __future__ import annotations

import re
import uuid

from app.engine.checks.base import CheckContext, CheckOutcome
from app.models import Confidence, Profile, Severity, Status

AL = Profile.ACTIVE_LIGHT
EVIL = "https://evil.pentestchess.invalid"  # dominio reservado (.invalid): nunca resolve


async def cors(ctx: CheckContext) -> CheckOutcome:
    probes = [
        ctx.get("/", profile=AL, headers={"Origin": EVIL}, note=f"Origin enviado: {EVIL}"),
        ctx.get("/", profile=AL, headers={"Origin": "null"}, note="Origin enviado: null"),
        ctx.get("/", profile=AL, method="OPTIONS",
                headers={"Origin": EVIL, "Access-Control-Request-Method": "GET"},
                note=f"Preflight com Origin: {EVIL}"),
    ]
    results = [await p for p in probes]
    ok = [r for r in results if r.ok]
    ev = [r.evidence for r in ok]
    if not ok:
        return CheckOutcome(Status.INCONCLUSIVE, "Sem resposta aos testes de CORS.", confidence=Confidence.LOW)
    reflected = creds = wildcard = False
    for r in ok:
        acao = (r.response.headers.get("access-control-allow-origin") or "").strip()
        acac = (r.response.headers.get("access-control-allow-credentials") or "").lower() == "true"
        if acao in (EVIL, "null"):
            reflected, creds = True, creds or acac
        elif acao == "*":
            wildcard, creds = True, creds or acac
    rec = "Usar allowlist fixa de origens; nunca refletir o Origin recebido nem combinar * com credenciais."
    if reflected and creds:
        return CheckOutcome(Status.FAIL, "CORS reflete origem arbitraria COM credenciais: qualquer site le respostas autenticadas.",
                            rec, severity=Severity.HIGH, evidence=ev)
    if reflected:
        return CheckOutcome(Status.FAIL, "CORS reflete a origem enviada (inclui 'null').", rec,
                            severity=Severity.MEDIUM, evidence=ev)
    if wildcard and creds:
        return CheckOutcome(Status.FAIL, "CORS com * e credenciais habilitadas.", rec,
                            severity=Severity.HIGH, evidence=ev)
    if wildcard:
        return CheckOutcome(Status.WARNING, "CORS com * (aceitavel so para conteudo publico).", rec,
                            severity=Severity.LOW, evidence=ev)
    return CheckOutcome(Status.PASS, "CORS nao reflete origens arbitrarias.", evidence=ev)


async def http_methods(ctx: CheckContext) -> CheckOutcome:
    res = await ctx.get("/", profile=AL, method="OPTIONS")
    if not res.ok:
        return CheckOutcome(Status.INCONCLUSIVE, f"Sem resposta ao OPTIONS ({res.error}).", confidence=Confidence.LOW)
    allow = res.response.headers.get("allow")
    ev = [res.evidence]
    if not allow:
        return CheckOutcome(Status.INCONCLUSIVE, "O servidor nao informou o cabecalho Allow.",
                            confidence=Confidence.LOW, evidence=ev)
    methods = {m.strip().upper() for m in allow.split(",")}
    rec = "Desabilitar metodos desnecessarios. Nginx: limit_except GET POST { deny all; }"
    if methods & {"TRACE", "TRACK"}:
        return CheckOutcome(Status.FAIL, "Metodo TRACE/TRACK habilitado.", rec, severity=Severity.MEDIUM, evidence=ev)
    risky = methods & {"PUT", "DELETE", "PATCH", "CONNECT"}
    if risky:
        return CheckOutcome(Status.WARNING, "Metodos de escrita anunciados: " + ", ".join(sorted(risky)) + ".",
                            rec, evidence=ev)
    return CheckOutcome(Status.PASS, "Apenas metodos esperados anunciados.", evidence=ev)


async def git_exposed(ctx: CheckContext) -> CheckOutcome:
    res = await ctx.get("/.git/HEAD", profile=AL)
    if not res.ok:
        return CheckOutcome(Status.INCONCLUSIVE, f"Sem resposta ({res.error}).", confidence=Confidence.LOW)
    r, ev = res.response, [res.evidence]
    if r.status_code == 200 and r.text[:200].lstrip().startswith("ref:"):
        return CheckOutcome(Status.FAIL, "Repositorio Git exposto: /.git/HEAD acessivel publicamente.",
                            "Bloquear /.git no servidor web. Nginx: location ~ /\\.git { deny all; }", evidence=ev)
    return CheckOutcome(Status.PASS, "/.git/HEAD nao esta exposto.", evidence=ev)


async def env_exposed(ctx: CheckContext) -> CheckOutcome:
    res = await ctx.get("/.env", profile=AL)
    if not res.ok:
        return CheckOutcome(Status.INCONCLUSIVE, f"Sem resposta ({res.error}).", confidence=Confidence.LOW)
    r, ev = res.response, [res.evidence]
    looks_env = bool(re.search(r"^[A-Z][A-Z0-9_]*=", r.text[:2000], re.M))
    html = "html" in (r.headers.get("content-type") or "").lower()
    if r.status_code == 200 and looks_env and not html:
        return CheckOutcome(Status.FAIL, "Arquivo .env exposto (formato CHAVE=valor). Trate os segredos como vazados.",
                            "Remover o arquivo do webroot e rotacionar TODOS os segredos nele.", evidence=ev)
    if r.status_code == 200:
        return CheckOutcome(Status.PASS, "/.env responde 200 mas nao tem formato de .env (possivel soft-404).",
                            confidence=Confidence.MEDIUM, evidence=ev)
    return CheckOutcome(Status.PASS, "/.env nao esta exposto.", evidence=ev)


_TRACE_MARKERS = {
    "python-traceback": "Traceback (most recent call last)",
    "java-stacktrace": "at java.",
    "dotnet": "System.NullReferenceException",
    "php-error": "Fatal error:",
    "sql-error": "SQLSTATE",
    "node-stack": "node_modules/",
    "generic-stacktrace": "Stack trace",
}


async def error_page(ctx: CheckContext) -> CheckOutcome:
    res = await ctx.get(f"/pentest-chess-inexistente-{uuid.uuid4().hex[:8]}", profile=AL)
    if not res.ok:
        return CheckOutcome(Status.INCONCLUSIVE, f"Sem resposta ({res.error}).", confidence=Confidence.LOW)
    r = res.response
    body = r.text[:5000]
    hit = next((k for k, v in _TRACE_MARKERS.items() if v in body), None)
    if hit:
        res.evidence.note = f"Marcador de stack trace detectado: {hit}"
        return CheckOutcome(Status.FAIL, "Pagina de erro expoe stack trace/detalhes internos.",
                            "Desativar debug em producao e usar paginas de erro genericas.", evidence=[res.evidence])
    if r.status_code >= 500:
        return CheckOutcome(Status.WARNING, f"Rota inexistente gerou erro {r.status_code} (tratamento de excecao fraco).",
                            "Tratar rotas inexistentes com 404 generico.", severity=Severity.LOW, evidence=[res.evidence])
    return CheckOutcome(Status.PASS, "Pagina de erro generica, sem detalhes internos.", evidence=[res.evidence])

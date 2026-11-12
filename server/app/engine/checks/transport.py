"""Abertura (recon): HTTPS, certificado TLS e redirecionamento HTTP -> HTTPS."""

from __future__ import annotations

from urllib.parse import urlsplit

from app.engine.checks.base import CheckContext, CheckOutcome
from app.engine.scope import normalize_origin
from app.models import Confidence, Severity, Status


async def https_in_use(ctx: CheckContext) -> CheckOutcome:
    ev = [ctx.note_evidence("CONFIG origin", f"Esquema do alvo: {ctx.scheme}")]
    if ctx.scheme == "https":
        return CheckOutcome(Status.PASS, "O alvo e atendido por HTTPS.", evidence=ev)
    return CheckOutcome(
        Status.FAIL, "O alvo e atendido apenas por HTTP: o trafego trafega em texto claro.",
        "Habilitar HTTPS (certificado de AC confiavel) e redirecionar todo HTTP para HTTPS.", evidence=ev)


async def tls_certificate(ctx: CheckContext) -> CheckOutcome:
    if ctx.scheme != "https":
        return CheckOutcome(Status.INCONCLUSIVE, "Nao se aplica: o alvo nao usa HTTPS.",
                            confidence=Confidence.HIGH)
    base = await ctx.base()
    if base.error == "tls":  # o 'blunder' que antes derrubava a campanha (dossie #1)
        ev = [ctx.note_evidence("TLS handshake", "Validacao do certificado falhou (cadeia, expiracao ou hostname).")]
        return CheckOutcome(
            Status.FAIL, "A validacao do certificado TLS falhou.",
            "Instalar certificado valido emitido por AC confiavel, com cadeia completa e hostname correto.",
            evidence=ev)
    if not base.ok:
        return CheckOutcome(Status.INCONCLUSIVE, f"Nao foi possivel conectar ({base.error}).",
                            "Verificar disponibilidade do alvo.", confidence=Confidence.LOW)
    return CheckOutcome(Status.PASS, "Certificado TLS validado pela cadeia de confianca do sistema.",
                        evidence=[base.evidence] if base.evidence else [])


async def http_to_https_redirect(ctx: CheckContext) -> CheckOutcome:
    parts = urlsplit(ctx.origin)
    if ctx.scheme == "http":
        http_origin = ctx.origin
    elif normalize_origin(ctx.origin) and normalize_origin(ctx.origin).endswith(":443"):
        http_origin = f"http://{parts.hostname}"
    else:
        return CheckOutcome(Status.INCONCLUSIVE, "Porta nao padrao: a origem HTTP equivalente e desconhecida.",
                            confidence=Confidence.LOW)
    if not ctx.guard.origin_in_scope(http_origin):
        return CheckOutcome(
            Status.INCONCLUSIVE, "A origem HTTP nao esta no escopo autorizado; teste nao executado.",
            f"Para testar, autorize {http_origin} em extra_origins.", confidence=Confidence.LOW)
    res = await ctx.get("/", origin=http_origin)
    if not res.ok:
        return CheckOutcome(Status.INCONCLUSIVE, f"Sem resposta na origem HTTP ({res.error}).",
                            confidence=Confidence.LOW)
    resp, ev = res.response, [res.evidence]
    loc = resp.headers.get("location", "")
    if resp.status_code in (301, 302, 303, 307, 308) and loc.lower().startswith("https://"):
        return CheckOutcome(Status.PASS, f"HTTP redireciona para HTTPS ({resp.status_code}).",
                            evidence=ev, exemplary=resp.status_code in (301, 308))
    return CheckOutcome(
        Status.FAIL, "A origem HTTP nao redireciona para HTTPS.",
        "Redirecionar HTTP -> HTTPS com 301. Nginx: return 301 https://$host$request_uri;",
        severity=Severity.MEDIUM, evidence=ev)

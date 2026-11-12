"""Meio-jogo: cabecalhos de seguranca (OWASP A02 Security Misconfiguration)."""

from __future__ import annotations

import re

from app.engine.checks.base import CheckContext, CheckOutcome, need_base
from app.models import Confidence, Severity, Status


def _ev(base) -> list:
    return [base.evidence] if base.evidence else []


async def hsts(ctx: CheckContext) -> CheckOutcome:
    if ctx.scheme != "https":
        return CheckOutcome(Status.INCONCLUSIVE, "HSTS so vale sobre HTTPS; alvo esta em HTTP.")
    resp, base, early = await need_base(ctx)
    if early:
        return early
    value = resp.headers.get("strict-transport-security")
    rec = "Nginx: add_header Strict-Transport-Security \"max-age=31536000; includeSubDomains\" always;"
    if not value:
        return CheckOutcome(Status.FAIL, "Cabecalho Strict-Transport-Security ausente.", rec, evidence=_ev(base))
    m = re.search(r"max-age=(\d+)", value, re.I)
    max_age = int(m.group(1)) if m else 0
    if max_age < 15552000:
        return CheckOutcome(Status.WARNING, f"HSTS com max-age curto ({max_age}s; recomendado >= 15552000).",
                            rec, evidence=_ev(base))
    sub = "includesubdomains" in value.lower()
    return CheckOutcome(Status.PASS, "HSTS configurado corretamente.", evidence=_ev(base),
                        exemplary=max_age >= 31536000 and sub)


def _parse_csp(value: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for part in value.split(";"):
        tokens = part.strip().split()
        if tokens:
            out[tokens[0].lower()] = [t.lower() for t in tokens[1:]]
    return out


async def csp(ctx: CheckContext) -> CheckOutcome:
    resp, base, early = await need_base(ctx)
    if early:
        return early
    enforced = resp.headers.get("content-security-policy")
    report_only = resp.headers.get("content-security-policy-report-only")
    rec = "Definir Content-Security-Policy enforcada. Ex.: default-src 'self'; object-src 'none'; frame-ancestors 'self'"
    if not enforced:
        why = "CSP apenas em Report-Only: nao bloqueia nada." if report_only else "Cabecalho Content-Security-Policy ausente."
        return CheckOutcome(Status.FAIL, why, rec, evidence=_ev(base))
    d = _parse_csp(enforced)
    script = d.get("script-src") or d.get("default-src") or []
    problems = []
    if "'unsafe-inline'" in script:
        problems.append("'unsafe-inline'")
    if "'unsafe-eval'" in script:
        problems.append("'unsafe-eval'")
    if "*" in script:
        problems.append("curinga '*'")
    if "default-src" not in d and "script-src" not in d:
        problems.append("sem default-src/script-src")
    if problems:
        return CheckOutcome(Status.WARNING, "CSP presente mas fraca: " + ", ".join(problems) + ".",
                            rec, evidence=_ev(base))
    return CheckOutcome(Status.PASS, "CSP enforcada, sem diretivas inseguras.", evidence=_ev(base),
                        exemplary="frame-ancestors" in d and "object-src" in d)


async def clickjacking(ctx: CheckContext) -> CheckOutcome:
    resp, base, early = await need_base(ctx)
    if early:
        return early
    xfo = (resp.headers.get("x-frame-options") or "").strip().upper()
    csp_v = resp.headers.get("content-security-policy") or ""
    has_fa = "frame-ancestors" in _parse_csp(csp_v)
    rec = "Usar CSP frame-ancestors 'self' (sucessor do X-Frame-Options). Nginx: add_header X-Frame-Options SAMEORIGIN always;"
    if has_fa:
        return CheckOutcome(Status.PASS, "Protecao contra clickjacking via CSP frame-ancestors.",
                            evidence=_ev(base), exemplary=True)
    if xfo in ("DENY", "SAMEORIGIN"):
        return CheckOutcome(Status.PASS, f"X-Frame-Options {xfo} (legado; prefira frame-ancestors).",
                            evidence=_ev(base))
    if xfo.startswith("ALLOW-FROM"):
        return CheckOutcome(Status.WARNING, "X-Frame-Options ALLOW-FROM e obsoleto e ignorado pelos navegadores.",
                            rec, evidence=_ev(base))
    if xfo:
        return CheckOutcome(Status.WARNING, "X-Frame-Options com valor invalido.", rec, evidence=_ev(base))
    return CheckOutcome(Status.FAIL, "Sem X-Frame-Options nem CSP frame-ancestors: pagina pode ser enquadrada.",
                        rec, evidence=_ev(base))


async def misc_headers(ctx: CheckContext) -> CheckOutcome:
    resp, base, early = await need_base(ctx)
    if early:
        return early
    h = resp.headers
    issues = []
    if (h.get("x-content-type-options") or "").lower() != "nosniff":
        issues.append("X-Content-Type-Options: nosniff ausente")
    if not h.get("referrer-policy"):
        issues.append("Referrer-Policy ausente")
    if not h.get("permissions-policy"):
        issues.append("Permissions-Policy ausente" + (" (Feature-Policy e obsoleto)" if h.get("feature-policy") else ""))
    xss = (h.get("x-xss-protection") or "").strip()
    if xss and xss != "0":
        issues.append("X-XSS-Protection esta obsoleto (enviar 0 ou omitir)")
    if issues:
        return CheckOutcome(
            Status.WARNING, "; ".join(issues) + ".",
            "Nginx: add_header X-Content-Type-Options nosniff always; add_header Referrer-Policy strict-origin-when-cross-origin always;",
            evidence=_ev(base))
    return CheckOutcome(Status.PASS, "Cabecalhos complementares presentes.", evidence=_ev(base), exemplary=True)


async def version_leak(ctx: CheckContext) -> CheckOutcome:
    resp, base, early = await need_base(ctx)
    if early:
        return early
    server = resp.headers.get("server") or ""
    powered = resp.headers.get("x-powered-by")
    leaks = []
    if re.search(r"\d+\.\d+", server):
        leaks.append("Server revela versao")
    if powered:
        leaks.append("X-Powered-By presente")
    if leaks:
        return CheckOutcome(Status.WARNING, "; ".join(leaks) + ".",
                            "Ocultar versoes. Nginx: server_tokens off; Express: app.disable('x-powered-by');",
                            evidence=_ev(base))
    return CheckOutcome(Status.PASS, "Nenhum vazamento de versao nos cabecalhos.", evidence=_ev(base),
                        confidence=Confidence.MEDIUM)

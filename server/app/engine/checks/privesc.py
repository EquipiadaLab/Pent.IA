"""Broken Access Control: recurso privilegiado alcancavel sem autorizacao.

Este check e a base para a tatica Privilege Escalation (MITRE ATT&CK TA0004)
no limite de um avaliador HTTP black-box. Ele NAO explora, nao injeta payload,
nao faz brute force e nao autentica. Ele apenas consulta, por GET, uma lista
FIXA e pequena de endpoints que normalmente exigem privilegio e registra
quando um deles devolve dados/funcionalidade privilegiada a um cliente
anonimo (OWASP A01:2025, WSTG-ATHZ-02).

Diferenca importante para SPAs: uma aplicacao de pagina unica responde 200 em
quase qualquer rota com o mesmo HTML. Por isso so classificamos como falha
quando a resposta expoe DADOS privilegiados (JSON com campos sensiveis ou
metricas operacionais), nunca por um simples 200 de HTML.

O corpo da resposta e lido apenas em memoria para classificar; ele nunca vai
para a evidencia (a evidencia guarda metodo, caminho, status, headers
sanitizados e o hash do corpo).
"""

from __future__ import annotations

from app.engine.checks.base import CheckContext, CheckOutcome
from app.models import Confidence, Profile, Severity, Status

AL = Profile.ACTIVE_LIGHT

# Lista FECHADA e curta de recursos que costumam exigir privilegio. Nao e
# wordlist nem enumeracao: sao caminhos conhecidos e estaveis.
PRIVILEGED_PATHS: tuple[str, ...] = (
    "/api/Users",
    "/rest/admin/application-configuration",
    "/metrics",
)

# Marcadores de DADOS privilegiados em JSON. Buscados em minusculas.
_DATA_MARKERS = ('"email"', '"password"', '"role"', '"isadmin"', '"totpsecret"', '"users"')


def _looks_like_metrics(body: str) -> bool:
    head = body.lstrip()[:200].lower()
    return head.startswith("# help") or head.startswith("# type") or "process_cpu_seconds" in body


def _exposes_privileged_data(content_type: str, body: str) -> bool:
    ctype = content_type.lower()
    sample = body[:5000].lower()
    if "json" in ctype and any(marker in sample for marker in _DATA_MARKERS):
        return True
    if _looks_like_metrics(body[:5000]):
        return True
    return False


async def unauthorized_privileged_access(ctx: CheckContext) -> CheckOutcome:
    """GET em uma lista fixa de endpoints privilegiados, sem autenticar."""
    exposed: list[str] = []
    enforced = 0
    evidence = []
    responded = 0

    for path in PRIVILEGED_PATHS:
        res = await ctx.get(path, profile=AL, note=f"Acesso anonimo a recurso privilegiado: {path}")
        if not res.ok:
            continue
        responded += 1
        evidence.append(res.evidence)
        resp = res.response
        if resp.status_code in (401, 403):
            enforced += 1
            continue
        if resp.status_code == 200 and _exposes_privileged_data(
            resp.headers.get("content-type", ""), resp.text
        ):
            exposed.append(path)

    rec = (
        "Exigir autenticacao e autorizacao de nivel adequado nesses endpoints; "
        "negar por padrao e validar o papel do usuario no servidor, nunca so no cliente."
    )
    if exposed:
        return CheckOutcome(
            Status.FAIL,
            "Recurso(s) privilegiado(s) acessivel(is) sem autenticacao: "
            + ", ".join(exposed)
            + ". Um usuario anonimo obtem dados/funcao que deveriam exigir privilegio.",
            rec,
            severity=Severity.HIGH,
            evidence=evidence,
        )
    if responded == 0:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            "Nenhum dos endpoints privilegiados conhecidos respondeu.",
            confidence=Confidence.LOW,
        )
    if enforced:
        return CheckOutcome(
            Status.PASS,
            "Os endpoints privilegiados testados exigem autorizacao (401/403) ou nao expoem dados.",
            evidence=evidence,
        )
    return CheckOutcome(
        Status.PASS,
        "Nenhum endpoint privilegiado conhecido expos dados a um cliente anonimo.",
        evidence=evidence,
    )

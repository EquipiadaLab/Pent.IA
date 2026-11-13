"""Checks passivos de reconhecimento de recursos publicos conhecidos.

Cada funcao consulta UM caminho fixo do mesmo alvo autorizado usando
``CheckContext.get``. Nao ha crawling, wordlist, fuzzing, subdominios,
consultas a terceiros ou tentativa de arquivos sensiveis.

Estes checks registram a superficie publica observada. A existencia de um
arquivo como robots.txt, sitemap.xml ou openapi.json nao e vulnerabilidade por
si so; por isso os resultados sao predominantemente informativos (Status.PASS)
e devem ser interpretados pelo relatorio como cobertura/descoberta, nao como
falha automatica.
"""

from __future__ import annotations

from app.engine.checks.base import CheckContext, CheckOutcome
from app.models import Confidence, Severity, Status


def _evidence(result, note: str):
    if result.evidence is not None:
        result.evidence.note = note
        return [result.evidence]
    return []


async def robots_txt(ctx: CheckContext) -> CheckOutcome:
    """Observa robots.txt sem tratar caminhos declarados como vulnerabilidade."""
    result = await ctx.get("/robots.txt")
    if not result.ok:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            f"Nao foi possivel consultar /robots.txt ({result.error}).",
            confidence=Confidence.LOW,
        )
    if result.response.status_code != 200:
        return CheckOutcome(
            Status.PASS,
            "/robots.txt nao foi publicado pelo alvo.",
            evidence=_evidence(result, "Recurso publico conhecido: /robots.txt (nao encontrado)."),
        )
    directives = sum(
        1
        for line in result.response.text[:50_000].splitlines()
        if line.strip().lower().startswith(("disallow:", "allow:", "sitemap:"))
    )
    return CheckOutcome(
        Status.PASS,
        f"/robots.txt esta publicamente disponivel ({directives} diretiva(s) observada(s)).",
        evidence=_evidence(result, "Recurso publico conhecido: /robots.txt."),
    )


async def sitemap_xml(ctx: CheckContext) -> CheckOutcome:
    """Observa sitemap.xml, sem enumerar URLs adicionais listadas nele."""
    result = await ctx.get("/sitemap.xml")
    if not result.ok:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            f"Nao foi possivel consultar /sitemap.xml ({result.error}).",
            confidence=Confidence.LOW,
        )
    if result.response.status_code != 200:
        return CheckOutcome(
            Status.PASS,
            "/sitemap.xml nao foi publicado pelo alvo.",
            evidence=_evidence(result, "Recurso publico conhecido: /sitemap.xml (nao encontrado)."),
        )
    return CheckOutcome(
        Status.PASS,
        "/sitemap.xml esta publicamente disponivel.",
        evidence=_evidence(result, "Recurso publico conhecido: /sitemap.xml. URLs internas nao foram seguidas."),
    )


async def security_txt(ctx: CheckContext) -> CheckOutcome:
    """Verifica o canal publico recomendado para receber reportes de seguranca."""
    result = await ctx.get("/.well-known/security.txt")
    if not result.ok:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            f"Nao foi possivel consultar /.well-known/security.txt ({result.error}).",
            confidence=Confidence.LOW,
        )
    if result.response.status_code != 200:
        return CheckOutcome(
            Status.WARNING,
            "O alvo nao publica /.well-known/security.txt.",
            "Publicar security.txt com um canal de contato para relatorios de vulnerabilidade.",
            severity=Severity.LOW,
            evidence=_evidence(result, "Canal publico de seguranca nao encontrado."),
        )
    return CheckOutcome(
        Status.PASS,
        "O alvo publica /.well-known/security.txt.",
        evidence=_evidence(result, "Canal publico de seguranca encontrado."),
    )


async def openapi_documentation(ctx: CheckContext) -> CheckOutcome:
    """Observa a especificacao OpenAPI publica, sem chamar endpoints documentados."""
    result = await ctx.get("/openapi.json")
    if not result.ok:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            f"Nao foi possivel consultar /openapi.json ({result.error}).",
            confidence=Confidence.LOW,
        )
    if result.response.status_code != 200:
        return CheckOutcome(
            Status.PASS,
            "/openapi.json nao esta publicamente disponivel.",
            evidence=_evidence(result, "Documentacao OpenAPI publica nao encontrada."),
        )
    return CheckOutcome(
        Status.PASS,
        "Uma especificacao OpenAPI esta publicamente disponivel.",
        evidence=_evidence(
            result,
            "Documentacao OpenAPI publica encontrada. Endpoints descritos nao foram acessados.",
        ),
    )

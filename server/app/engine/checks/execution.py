"""Prova de conceito NAO-DESTRUTIVA de Server-Side Template Injection (TA0002).

Este check NAO executa comando de sistema, NAO sobe shell, NAO apaga ou
altera dados e NAO tenta negacao de servico. Ele envia uma expressao
aritmetica inofensiva (ex.: ``${{7*7}}``) em um parametro de busca conhecido
e verifica se o servidor AVALIOU a expressao (retornou ``49``) em vez de
apenas refletir o texto literal. Isso prova que existe um motor de template
interpretando entrada do usuario como codigo -- condicao necessaria para um
RCE real -- sem de fato executar codigo arbitrario no alvo.

Mapeamento MITRE: T1190 (Exploit Public-Facing Application) sob a tatica
Execution (TA0002), restrito a uma sondagem de prova de conceito.
"""

from __future__ import annotations

import re

from app.engine.checks.base import CheckContext, CheckOutcome
from app.models import Confidence, Profile, Severity, Status

AL = Profile.ACTIVE_LIGHT

# Pares (payload, resultado esperado se avaliado). Todos aritmeticos e
# inofensivos: nenhum deles le arquivo, chama processo ou rede.
_PROBES: tuple[tuple[str, str], ...] = (
    ("${{7*7}}", "49"),
    ("#{7*7}", "49"),
    ("{{7*7}}", "49"),
)


async def ssti_probe(ctx: CheckContext) -> CheckOutcome:
    """Sondagem de SSTI com expressao aritmetica inofensiva no campo de busca."""
    evidence = []
    hits: list[str] = []

    for payload, expected in _PROBES:
        res = await ctx.get(
            f"/rest/products/search?q={payload}",
            profile=AL,
            headers={"Accept": "application/json"},
            note=f"Sondagem SSTI nao-destrutiva (expressao aritmetica): {payload!r}",
        )
        if not res.ok:
            continue
        evidence.append(res.evidence)
        body = res.response.text[:5000]
        # So conta como evidencia de avaliacao se o resultado aritmetico
        # aparecer SEM o payload literal (ou seja, foi calculado, nao ecoado).
        if re.search(rf"\b{expected}\b", body) and payload not in body:
            hits.append(payload)

    rec = (
        "Nunca interpolar entrada do usuario diretamente em uma string de template; "
        "usar APIs de template que tratam a entrada como dado (ex.: render com contexto, "
        "nunca render(template_string_concatenada))."
    )
    if hits:
        return CheckOutcome(
            Status.FAIL,
            "O servidor avaliou expressao(oes) de template enviada(s) no campo de busca "
            f"({', '.join(hits)}), em vez de trata-la como texto. Isso indica Server-Side "
            "Template Injection: entrada do usuario e interpretada como codigo pelo motor de template.",
            rec,
            severity=Severity.HIGH,
            evidence=evidence,
        )
    if not evidence:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            "Nenhuma das sondagens recebeu resposta do endpoint de busca.",
            confidence=Confidence.LOW,
        )
    return CheckOutcome(
        Status.PASS,
        "Nenhuma das expressoes de template enviadas foi avaliada pelo servidor.",
        evidence=evidence,
    )

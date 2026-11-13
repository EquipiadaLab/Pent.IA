"""Superficie de manipulacao de dados: pre-condicao de Impacto (TA0040).

Este check e a base segura para a tatica Impact (MITRE ATT&CK TA0040) em um
avaliador HTTP black-box. As tecnicas de Impact sao destrutivas por natureza
(destruicao, criptografia, DoS, defacement). O Pent.IA NAO executa nenhuma
delas. Este check apenas consulta, por ``OPTIONS`` (metodo que NAO altera
estado), uma lista FIXA e pequena de endpoints de dados e registra quando eles
ANUNCIAM metodos destrutivos (PUT/DELETE/PATCH) a um cliente anonimo.

Isso e uma PRE-CONDICAO para T1565 (Data Manipulation), nao uma demonstracao.
O check nunca envia PUT, DELETE ou PATCH; nunca cria, altera ou remove dados.

Diferenca para METHOD-001: aquele avalia a higiene de metodos na raiz ``/``
(configuracao, A02). Este olha endpoints de DADOS com a pergunta de impacto:
"uma operacao destrutiva esta ao alcance de quem nao deveria?".
"""

from __future__ import annotations

from app.engine.checks.base import CheckContext, CheckOutcome
from app.models import Confidence, Profile, Severity, Status

AL = Profile.ACTIVE_LIGHT

# Lista FECHADA e curta de colecoes de dados comuns. Nao e wordlist nem
# enumeracao; sao caminhos conhecidos e estaveis.
DATA_ENDPOINTS: tuple[str, ...] = ("/api/Users", "/api/Products")

_DESTRUCTIVE = {"PUT", "DELETE", "PATCH"}


async def data_mutation_surface(ctx: CheckContext) -> CheckOutcome:
    """OPTIONS (nao-mutante) em endpoints de dados para medir superficie destrutiva."""
    exposed: dict[str, list[str]] = {}
    evidence = []
    responded = 0

    for path in DATA_ENDPOINTS:
        res = await ctx.get(
            path,
            profile=AL,
            method="OPTIONS",
            note=f"Metodos anunciados em {path} (somente OPTIONS; nada e alterado).",
        )
        if not res.ok:
            continue
        responded += 1
        evidence.append(res.evidence)
        allow = res.response.headers.get("allow")
        if not allow:
            continue
        methods = {m.strip().upper() for m in allow.split(",")}
        hit = sorted(methods & _DESTRUCTIVE)
        if hit:
            exposed[path] = hit

    rec = (
        "Restringir metodos destrutivos (PUT/DELETE/PATCH) e exigir autenticacao e "
        "autorizacao de nivel adequado para qualquer operacao que altere dados; negar por padrao."
    )
    if exposed:
        detalhe = "; ".join(f"{p}: {', '.join(m)}" for p, m in exposed.items())
        return CheckOutcome(
            Status.WARNING,
            f"Endpoints de dados anunciam metodos destrutivos ({detalhe}). E uma pre-condicao "
            "para manipulacao/destruicao de dados; o teste nao executou nenhuma alteracao.",
            rec,
            severity=Severity.MEDIUM,
            confidence=Confidence.MEDIUM,
            evidence=evidence,
        )
    if responded == 0:
        return CheckOutcome(
            Status.INCONCLUSIVE,
            "Nenhum endpoint de dados conhecido respondeu ao OPTIONS.",
            confidence=Confidence.LOW,
        )
    return CheckOutcome(
        Status.PASS,
        "Os endpoints de dados testados nao anunciam metodos destrutivos a um cliente anonimo.",
        evidence=evidence,
    )

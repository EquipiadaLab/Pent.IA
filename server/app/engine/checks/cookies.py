"""Flags de cookies (WSTG-SESS-02). Valores NUNCA sao guardados: so nome e flags."""

from __future__ import annotations

import re

from app.engine.checks.base import CheckContext, CheckOutcome, need_base
from app.models import Confidence, Status

_SESSION = re.compile(r"sess|sid|auth|token|jwt|login", re.I)


def parse_cookie(raw: str) -> tuple[str, dict[str, str]]:
    head, *attrs = [p.strip() for p in raw.split(";")]
    name = head.split("=", 1)[0].strip()
    flags: dict[str, str] = {}
    for a in attrs:
        k, _, v = a.partition("=")
        flags[k.strip().lower()] = v.strip().lower()
    return name, flags


async def cookie_flags(ctx: CheckContext) -> CheckOutcome:
    resp, base, early = await need_base(ctx)
    if early:
        return early
    ev = [base.evidence] if base.evidence else []
    raw_cookies = resp.headers.get_list("set-cookie")
    if not raw_cookies:
        return CheckOutcome(Status.INCONCLUSIVE, "Nenhum cookie definido em GET /; nada a avaliar.",
                            confidence=Confidence.LOW, evidence=ev)
    https = ctx.scheme == "https"
    fails: list[str] = []
    warns: list[str] = []
    for raw in raw_cookies:
        name, f = parse_cookie(raw)
        session = bool(_SESSION.search(name))
        same = f.get("samesite")
        if https and "secure" not in f:
            fails.append(f"{name}: sem Secure")
        if same == "none" and "secure" not in f:
            fails.append(f"{name}: SameSite=None sem Secure")
        if "httponly" not in f:
            (fails if session else warns).append(f"{name}: sem HttpOnly")
        if same is None:
            warns.append(f"{name}: sem SameSite")
        elif same == "none":
            warns.append(f"{name}: SameSite=None")
    rec = "Definir flags: Set-Cookie: sid=...; Secure; HttpOnly; SameSite=Lax"
    if fails:
        return CheckOutcome(Status.FAIL, "Cookies inseguros: " + "; ".join(fails + warns) + ".", rec, evidence=ev)
    if warns:
        return CheckOutcome(Status.WARNING, "Cookies com ressalvas: " + "; ".join(warns) + ".", rec, evidence=ev)
    return CheckOutcome(Status.PASS, "Cookies com Secure, HttpOnly e SameSite.", evidence=ev, exemplary=True)

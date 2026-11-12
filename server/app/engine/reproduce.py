"""Passos de reproducao (item 7): comandos curl equivalentes as requisicoes do lance.

Gerados a partir das evidencias ja mascaradas: so GET/OPTIONS e so caminhos.
"""

from __future__ import annotations

import re

from app.models import Move

_ORIGIN_NOTE = re.compile(r"Origin(?: enviado)?: (\S+)")


def reproduce_steps(origin: str, move: Move) -> list[str]:
    cmds: list[str] = []
    base = origin.rstrip("/")
    for ev in move.evidence:
        parts = ev.request.split()
        if len(parts) < 2 or parts[0] not in ("GET", "OPTIONS"):
            continue
        method, path = parts[0], parts[1]
        extra = ""
        m = _ORIGIN_NOTE.search(ev.note or "")
        if m:
            extra = f' -H "Origin: {m.group(1)}"'
        flag = "-X OPTIONS " if method == "OPTIONS" else ""
        cmds.append(f'curl -i {flag}"{base}{path}"{extra}')
    return list(dict.fromkeys(cmds))

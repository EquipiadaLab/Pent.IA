"""Configuracoes de escopo geridas pelo admin em tempo de execucao.

Guarda, em memoria e persistido no banco (tabela ``app_settings``), as duas
listas que um usuario ``admin`` pode editar pela tela:

- ``authorized_targets``: URLs/origens autorizadas. Quando nao vazia, o sistema
  passa a aceitar SOMENTE esses alvos (modo lista fixa), somando-se ao que vier
  do ``.env`` (``AUTHORIZED_TARGETS``).
- ``blocked_scopes``: hosts/origens SEMPRE recusados, em qualquer modo (reforca
  o anti-SSRF que ja bloqueia rede interna).

``authorization.py`` consulta este cache (sincrono) a cada decisao. O cache e
carregado do banco no startup e atualizado quando o admin salva.
"""

from __future__ import annotations

import threading

AUTHORIZED_KEY = "authorized_targets"
BLOCKED_KEY = "blocked_scopes"

_LOCK = threading.Lock()
_STATE: dict[str, list[str]] = {AUTHORIZED_KEY: [], BLOCKED_KEY: []}


def _clean(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for item in values:
        text = str(item).strip()
        if text and text not in out:
            out.append(text)
    return out


def load(settings: dict[str, object]) -> None:
    """Carrega o cache a partir do banco (dict de app_settings)."""
    with _LOCK:
        _STATE[AUTHORIZED_KEY] = _clean(settings.get(AUTHORIZED_KEY))
        _STATE[BLOCKED_KEY] = _clean(settings.get(BLOCKED_KEY))


def set_values(authorized: object, blocked: object) -> dict[str, list[str]]:
    """Atualiza o cache e devolve o estado limpo (para persistir no banco)."""
    with _LOCK:
        _STATE[AUTHORIZED_KEY] = _clean(authorized)
        _STATE[BLOCKED_KEY] = _clean(blocked)
        return {
            AUTHORIZED_KEY: list(_STATE[AUTHORIZED_KEY]),
            BLOCKED_KEY: list(_STATE[BLOCKED_KEY]),
        }


def authorized_targets() -> list[str]:
    with _LOCK:
        return list(_STATE[AUTHORIZED_KEY])


def blocked_scopes() -> list[str]:
    with _LOCK:
        return list(_STATE[BLOCKED_KEY])

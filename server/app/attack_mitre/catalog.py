"""Leitura em memoria do catalogo ATT&CK (sem rede) para os agentes.

O agente de tatica so le daqui -- nunca baixa nada em tempo de campanha.
Isso mantem a regra do projeto de "o motor nao depende de rede externa alem
do proprio alvo autorizado" e evita falha de demo por internet do evento.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.schemas.agents_contract import AttackReference

CACHE_PATH = Path(__file__).parent / "attack_cache.json"


class AttackCatalogUnavailable(RuntimeError):
    """O cache local ainda nao foi gerado (rode o updater uma vez)."""


class AttackCatalog:
    def __init__(self, data: dict):
        self._tactics: dict[str, dict] = {t["tactic_id"]: t for t in data.get("tactics", [])}
        self._techniques: dict[str, dict] = {t["technique_id"]: t for t in data.get("techniques", [])}

    # -- consultas que os agentes usam -----------------------------------
    def tactic(self, tactic_id: str) -> dict | None:
        return self._tactics.get(tactic_id)

    def tactic_by_shortname(self, shortname: str) -> dict | None:
        for t in self._tactics.values():
            if t.get("shortname") == shortname:
                return t
        return None

    def technique(self, technique_id: str) -> dict | None:
        return self._techniques.get(technique_id)

    def techniques_for_tactic(self, tactic_id: str) -> list[dict]:
        """Todas as tecnicas (e sub-tecnicas) daquela tatica, por TAxxxx."""
        return [t for t in self._techniques.values() if tactic_id in t.get("tactic_ids", [])]

    def reference_for(self, technique_id: str, tactic_id: str | None = None) -> AttackReference:
        """Monta um ``AttackReference`` pronto para usar em um ``Finding``.

        Se ``tactic_id`` nao for informado, usa a primeira tatica associada
        a tecnica (a maioria das tecnicas do MVP tem so uma).
        """
        technique = self.technique(technique_id)
        if technique is None:
            raise KeyError(f"Tecnica desconhecida no catalogo local: {technique_id}")

        resolved_tactic_id = tactic_id or (technique["tactic_ids"][0] if technique["tactic_ids"] else None)
        tactic = self.tactic(resolved_tactic_id) if resolved_tactic_id else None

        return AttackReference(
            tactic_id=resolved_tactic_id or "",
            tactic_name=(tactic or {}).get("name", ""),
            technique_id=technique["technique_id"],
            technique_name=technique["name"],
            url=technique.get("url"),
        )

    @property
    def tactics(self) -> list[dict]:
        return list(self._tactics.values())


@lru_cache(maxsize=1)
def get_catalog(path: Path = CACHE_PATH) -> AttackCatalog:
    """Carrega o catalogo uma vez por processo (cache em memoria)."""
    if not path.exists():
        raise AttackCatalogUnavailable(
            f"{path} nao existe. Rode: python -m app.attack_mitre.updater"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return AttackCatalog(data)

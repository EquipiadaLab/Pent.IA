"""Baixa o dataset STIX do MITRE ATT&CK e grava um cache local resumido.

Fonte oficial (ver https://attack.mitre.org/resources/attack-data-and-tools/):
o mesmo repositorio que alimenta o site e o ATT&CK Navigator.

Rodar manualmente quando precisar atualizar o catalogo (nao roda a cada
request da API -- o cache e lido do disco):

    cd server
    .venv/bin/python -m app.attack_mitre.updater

Isso baixa ~55 MB uma unica vez e grava ``attack_cache.json`` (~485 KB) na
mesma pasta deste modulo. O cache resumido E versionado no git: assim o
sistema funciona offline (clone, merge, demo) sem depender da internet do
evento. So rode o updater quando quiser atualizar para uma nova versao do
ATT&CK e commite o resultado.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("pentest_chess.attack_mitre")

# "enterprise-attack" cobre tecnicas contra redes corporativas/web, que e o
# dominio relevante para o Pentest Chess (web app). Os outros dominios do
# ATT&CK (ICS, mobile) nao se aplicam ao MVP.
DEFAULT_SOURCE_URL = (
    "https://raw.githubusercontent.com/mitre-attack/attack-stix-data/master/"
    "enterprise-attack/enterprise-attack.json"
)

CACHE_PATH = Path(__file__).parent / "attack_cache.json"


def _tactic_shortname_to_id(objects: list[dict[str, Any]]) -> dict[str, str]:
    """x-mitre-tactic tem o ATT&CK ID (TAxxxx) separado do shortname usado
    nas kill_chain_phases das tecnicas. Monta o mapa shortname -> TAxxxx."""
    mapping: dict[str, str] = {}
    for obj in objects:
        if obj.get("type") != "x-mitre-tactic":
            continue
        shortname = obj.get("x_mitre_shortname")
        attack_id = _external_attack_id(obj)
        if shortname and attack_id:
            mapping[shortname] = attack_id
    return mapping


def _external_attack_id(obj: dict[str, Any]) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("external_id")
    return None


def _external_url(obj: dict[str, Any]) -> str | None:
    for ref in obj.get("external_references", []):
        if ref.get("source_name") == "mitre-attack":
            return ref.get("url")
    return None


def _build_catalog(stix_bundle: dict[str, Any]) -> dict[str, Any]:
    """Reduz o bundle STIX completo a {tactics: [...], techniques: [...]}."""
    objects: list[dict[str, Any]] = stix_bundle.get("objects", [])

    tactics: list[dict[str, Any]] = []
    for obj in objects:
        if obj.get("type") != "x-mitre-tactic" or obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        attack_id = _external_attack_id(obj)
        if not attack_id:
            continue
        tactics.append(
            {
                "tactic_id": attack_id,
                "shortname": obj.get("x_mitre_shortname"),
                "name": obj.get("name"),
                "description": (obj.get("description") or "").split("\n")[0][:400],
                "url": _external_url(obj),
            }
        )

    shortname_to_tactic_id = _tactic_shortname_to_id(objects)

    techniques: list[dict[str, Any]] = []
    for obj in objects:
        if obj.get("type") != "attack-pattern" or obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue
        attack_id = _external_attack_id(obj)
        if not attack_id:
            continue
        tactic_ids = sorted(
            {
                shortname_to_tactic_id[phase["phase_name"]]
                for phase in obj.get("kill_chain_phases", [])
                if phase.get("kill_chain_name") == "mitre-attack"
                and phase.get("phase_name") in shortname_to_tactic_id
            }
        )
        techniques.append(
            {
                "technique_id": attack_id,
                "name": obj.get("name"),
                "is_subtechnique": bool(obj.get("x_mitre_is_subtechnique")),
                "tactic_ids": tactic_ids,
                "description": (obj.get("description") or "").split("\n")[0][:400],
                "url": _external_url(obj),
                "platforms": obj.get("x_mitre_platforms", []),
            }
        )

    return {
        "source": DEFAULT_SOURCE_URL,
        "tactics": sorted(tactics, key=lambda t: t["tactic_id"]),
        "techniques": sorted(techniques, key=lambda t: t["technique_id"]),
    }


def update_cache(source_url: str = DEFAULT_SOURCE_URL, dest: Path = CACHE_PATH) -> Path:
    """Baixa o STIX bundle e grava o catalogo resumido em ``dest``.

    Idempotente: pode ser rodado de novo para atualizar quando o MITRE
    publicar uma nova versao do ATT&CK.
    """
    logger.info("Baixando dataset ATT&CK de %s", source_url)
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        resp = client.get(source_url)
        resp.raise_for_status()
        bundle = resp.json()

    catalog = _build_catalog(bundle)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "Catalogo ATT&CK salvo em %s (%d taticas, %d tecnicas)",
        dest,
        len(catalog["tactics"]),
        len(catalog["techniques"]),
    )
    return dest


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    path = update_cache()
    print(f"OK: {path} ({os.path.getsize(path) / 1024:.1f} KB)")

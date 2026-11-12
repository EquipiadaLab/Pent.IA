"""Catalogo local do MITRE ATT&CK (taticas e tecnicas) para os agentes.

Nao existe uma "API REST" oficial do ATT&CK para consulta simples: os dados
sao publicados como STIX (JSON) no GitHub (mitre-attack/attack-stix-data).
A estrategia deste modulo e:

1. ``update_cache()`` baixa o dataset "enterprise-attack" uma vez, filtra so
   os campos que os agentes precisam (tatica, tecnica, sub-tecnica,
   descricao, URL) e grava um JSON pequeno em ``attack_cache.json``
   (fora do Git; o dataset completo tem ~55 MB).
2. ``AttackCatalog`` le esse cache e responde consultas em memoria,
   sem rede, para o agente nao depender de internet durante a campanha.

Uso tipico num agente de tatica:

    from app.attack_mitre import get_catalog
    catalog = get_catalog()
    techniques = catalog.techniques_for_tactic("reconnaissance")
"""

from .catalog import AttackCatalog, get_catalog
from .updater import update_cache

__all__ = ["AttackCatalog", "get_catalog", "update_cache"]

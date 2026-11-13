"""Contrato publico da correlacao CVE (saida JSON do /report e /campaigns/{id}/cves)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExploitReference(BaseModel):
    """Um link de exploit/PoC, so incluido quando a propria NVD o rotula como tal
    (tag ``Exploit`` nas ``references`` do registro CVE)."""

    url: str
    source: str | None = Field(default=None, description="Dominio/origem da referencia, ex.: 'github.com'")


class CveReference(BaseModel):
    """Um CVE correlacionado a um achado, com dados oficiais da NVD (nunca inventados)."""

    cve_id: str
    description: str
    cvss_score: float | None = None
    cvss_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None
    cvss_vector: str | None = None
    cwe_ids: list[str] = Field(default_factory=list)
    published: str | None = None
    nvd_url: str
    exploits: list[ExploitReference] = Field(default_factory=list)


class CveMatch(BaseModel):
    """Resultado da correlacao para UM termo de busca (ex.: 1 header observado)."""

    search_term: str = Field(description="Termo realmente observado que gerou a busca, ex.: 'nginx 1.14.0'.")
    move: int | None = Field(default=None, description="Lance que originou o termo, se houver.")
    cves: list[CveReference] = Field(default_factory=list)
    queried_at: str
    source: Literal["nvd"] = "nvd"
    error: str | None = Field(default=None, description="Motivo da falha, se a consulta nao completou.")

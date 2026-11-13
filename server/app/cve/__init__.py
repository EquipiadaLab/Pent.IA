"""Correlacao de achados com CVEs publicos (NVD) e exploits conhecidos.

Este modulo NUNCA inventa um CVE. Ele consulta a API publica do NIST NVD
(https://services.nvd.nist.gov/rest/json/cves/2.0) usando apenas termos
observados de verdade pelo Motor (ex.: "Server: nginx/1.14.0" capturado por
INFO-001/Discovery). Se a NVD nao retornar nada, o achado simplesmente nao
tem CVEs associados -- nunca ha "preenchimento" generico por categoria.
"""

from app.cve.models import CveMatch, CveReference, ExploitReference
from app.cve.nvd_client import NvdClient, build_search_term

__all__ = ["CveMatch", "CveReference", "ExploitReference", "NvdClient", "build_search_term"]

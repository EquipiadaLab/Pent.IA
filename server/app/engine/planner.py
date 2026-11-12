"""Planner: decide QUAIS lances jogar e em que ordem, conforme o que observa.

Deterministico e fechado: so escolhe dentro do CATALOG. (Ponto de extensao
para o LLM: ``suggest`` pode propor um test_id; o executor valida contra o
catalogo antes de rodar. O LLM nunca cria requisicoes.)
"""

from __future__ import annotations

from app.engine.checks import CATALOG
from app.engine.checks.base import CheckContext, CheckSpec
from app.models import CampaignConfig, Phase

_PHASE_ORDER = {Phase.OPENING: 0, Phase.MIDDLEGAME: 1, Phase.ENDGAME: 2}
# Lances que ainda fazem sentido mesmo com o alvo inacessivel por HTTPS.
_INDEPENDENT = {"TLS-001", "TLS-002", "REDIR-001"}


class Planner:
    def __init__(self, config: CampaignConfig, catalog: list[CheckSpec] | None = None) -> None:
        self.config = config
        self.catalog = {c.test_id: c for c in (catalog or CATALOG)}

    def plan(self) -> list[CheckSpec]:
        """Ordem base: abertura -> meio-jogo -> final (estavel dentro da fase)."""
        return sorted(self.catalog.values(), key=lambda s: _PHASE_ORDER[s.phase])

    def suggest(self, test_id: str) -> CheckSpec | None:
        """Valida uma sugestao externa (ex.: LLM) contra o catalogo fechado."""
        return self.catalog.get(test_id)

    def skip_reason(self, spec: CheckSpec, ctx: CheckContext) -> str | None:
        """Motivo para NAO jogar o lance agora (None = pode jogar)."""
        if spec.profile not in self.config.allowed_profiles:
            return f"Perfil {spec.profile.value} nao permitido nesta campanha."
        if ctx.base_failed and spec.test_id not in _INDEPENDENT:
            return "Alvo inacessivel: lance nao executado."
        return None

"""Contexto da aplicacao: dependencias compartilhadas pelas rotas (Trilho B).

Guardado em ``app.state.ctx`` e injetado nas rotas via ``get_ctx``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from fastapi import Request

from app.config import Settings
from app.cve.nvd_client import NvdClient
from app.db import Database
from app.interfaces import CampaignRunner
from app.reporter import ReportBuilder
from app.sink import Coordinator


@dataclass
class AppContext:
    settings: Settings
    db: Database
    coordinator: Coordinator
    runner: CampaignRunner
    report_builder: ReportBuilder
    using_real_engine: bool = False
    nvd_client: NvdClient | None = None
    _tasks: set[asyncio.Task] = field(default_factory=set)

    def launch_campaign(self, campaign_id: str, config) -> None:
        """Dispara a execucao da campanha em segundo plano."""
        sink = self.coordinator.new_sink(campaign_id)
        task = asyncio.create_task(
            self.runner(campaign_id, config, sink), name=f"run:{campaign_id}"
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def shutdown(self) -> None:
        for task in list(self._tasks):
            task.cancel()
        self.db.close()


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx

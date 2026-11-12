"""Aplicacao FastAPI da Plataforma (Trilho B).

Monta o contexto, escolhe o ``run_campaign`` (motor real se disponivel,
senao o fake de exemplo) e expoe as rotas. CORS liberado para o frontend.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.api.context import AppContext
from app.config import load_settings
from app.db import Database
from app.interfaces import CampaignRunner
from app.reporter import ReportBuilder, build_llm_client
from app.sink import Coordinator

logger = logging.getLogger("pentest_chess")


def _resolve_runner() -> tuple[CampaignRunner, bool]:
    """Usa o motor real (Trilho A) se ``app.engine.runner.run_campaign``
    existir; caso contrario, o fake de exemplo da Plataforma."""
    try:
        from app.engine.runner import run_campaign  # type: ignore

        logger.info("Usando motor real: app.engine.runner.run_campaign")
        return run_campaign, True
    except Exception:
        from app.sample_runner import run_campaign

        logger.warning(
            "Motor real indisponivel; usando run_campaign de exemplo (app.sample_runner)."
        )
        return run_campaign, False


def build_context() -> AppContext:
    settings = load_settings()
    db = Database(settings.database_path)
    coordinator = Coordinator(db)
    runner, using_real = _resolve_runner()
    report_builder = ReportBuilder(build_llm_client(settings))
    return AppContext(
        settings=settings,
        db=db,
        coordinator=coordinator,
        runner=runner,
        report_builder=report_builder,
        using_real_engine=using_real,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = build_context()
    app.state.ctx = ctx
    try:
        yield
    finally:
        await ctx.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="Pentest Chess — Plataforma", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # dev; restrinja em producao
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, object]:
        ctx: AppContext = app.state.ctx
        return {
            "status": "ok",
            "engine": "real" if ctx.using_real_engine else "sample",
            "llm": "bedrock" if ctx.settings.llm_enabled else "template",
        }

    return app


app = create_app()

"""Aplicacao FastAPI da Plataforma (Trilho B).

Monta o contexto, escolhe o ``run_campaign`` (motor real se disponivel,
senao o fake de exemplo) e expoe as rotas. CORS liberado para o frontend.
"""

from __future__ import annotations

import functools
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import admin_settings
from app.api import router
from app.api.admin_routes import router as admin_router
from app.api.auth_routes import router as auth_router
from app.api.info import router as info_router
from app.api.timeline import router as timeline_router
from app.api.ws import router as ws_router
from app.api.context import AppContext
from app.auth import ensure_seed_admin
from app.config import cors_origins, load_settings
from app.cve.nvd_client import NvdClient
from app.db import Database
from app.interfaces import CampaignRunner
from app.reporter import BedrockLLMClient, ReportBuilder, build_llm_client
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
    llm = build_llm_client(settings)
    if using_real and settings.planner_model_id:
        # Agente autonomo: a IA planeja cada lance (modelo rapido); o motor arbitra.
        planner_llm = BedrockLLMClient(settings.planner_model_id, settings.aws_region)
        runner = functools.partial(runner, llm=planner_llm)
    report_builder = ReportBuilder(llm, db=db, judge=llm)
    return AppContext(
        settings=settings,
        db=db,
        coordinator=coordinator,
        runner=runner,
        report_builder=report_builder,
        using_real_engine=using_real,
        nvd_client=NvdClient(api_key=settings.nvd_api_key),
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    ctx = build_context()
    app.state.ctx = ctx
    # Carrega o escopo gerido pelo admin e garante um admin inicial.
    admin_settings.load(ctx.db.all_settings_sync())
    await ensure_seed_admin(ctx.db)
    try:
        yield
    finally:
        await ctx.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="PENT.IA — Plataforma", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(),  # so a tela (Vite); ajuste CORS_ORIGINS no .env
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    app.include_router(router)
    app.include_router(ws_router)
    app.include_router(timeline_router)
    app.include_router(info_router)
    app.include_router(auth_router)
    app.include_router(admin_router)

    @app.get("/health")
    async def health() -> dict[str, object]:
        ctx: AppContext = app.state.ctx
        return {
            "status": "ok",
            "engine": "real" if ctx.using_real_engine else "sample",
            "llm": "bedrock" if ctx.settings.llm_enabled else "template",
            "planner": "ai" if ctx.using_real_engine and ctx.settings.planner_model_id else "rules",
        }

    return app


app = create_app()

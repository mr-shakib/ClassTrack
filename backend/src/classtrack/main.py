"""Application factory."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from classtrack.api.v1.router import api_router
from classtrack.core.config import get_settings
from classtrack.core.errors import register_exception_handlers
from classtrack.core.logging import configure_logging
from classtrack.db.session import dispose_engine

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # noqa: ARG001
    """Run the status sweep alongside the app, and shut it down cleanly."""
    settings = get_settings()
    task: asyncio.Task[None] | None = None

    if settings.sweep_interval_seconds > 0:
        from classtrack.services.sweep import sweep_loop

        task = asyncio.create_task(sweep_loop(settings.sweep_interval_seconds))
        logger.info("Status sweep started (every %ss)", settings.sweep_interval_seconds)

    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await dispose_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
        description="Department class monitoring and makeup management for DIU CSE.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()

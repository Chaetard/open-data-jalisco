# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from ..shared.config import get_settings
from ..shared.logging import configure_logging, get_logger
from .routers import (
    ask,
    documents,
    health,
    manifests,
    search,
    source,
    sources,
    stats,
)

logger = get_logger(__name__)


def _warmup() -> None:
    """Load the embedder and reranker models at boot, not on the first query.

    Measured cold start on CPU is ~18 s (model weights load lazily on first
    use); paying it here means the first real user query is warm (~2-3 s) and
    doesn't trip frontend timeouts. Best-effort: dummy/none providers load
    nothing, and any failure (e.g. sentence-transformers not installed) is
    logged without blocking boot.
    """
    try:
        from .deps import get_embedding_provider, get_reranker

        get_embedding_provider().embed_query("warmup")
        reranker = get_reranker()
        if reranker is not None:
            reranker.rerank("warmup", ["warmup"])
        logger.info("model warmup complete")
    except Exception:
        logger.warning("model warmup skipped", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Skip warmup under test: every API test injects fakes via
    # dependency_overrides, and warmup would otherwise load the real models
    # (bypassing those overrides). In prod there are no overrides → it runs.
    if not app.dependency_overrides:
        _warmup()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="open-data-jalisco",
        version=__version__,
        description=(
            "Technical API for the open-data-jalisco platform. Exposes documents, "
            "sources, semantic search and integrity manifests."
        ),
        # Prefijo externo cuando corre tras el proxy (Caddy /api/*). Vacío en dev.
        root_path=settings.root_path,
        lifespan=lifespan,
    )

    # CORS for the SPA. The frontend lives on a different origin during dev
    # (Vite on :5173, API on :8000) so the browser blocks requests unless we
    # whitelist the origin here. Origins come from settings so prod stays
    # explicit instead of accidentally allowing "*".
    allowed_origins = [
        o.strip() for o in settings.cors_origins.split(",") if o.strip()
    ]
    if allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "Accept"],
        )

    # Log every request's start and finish with duration. A request that hangs
    # (slow upstream, runaway agent loop) leaves the "start" line with no
    # "done" - exactly the signal that was missing when a query just timed out.
    @app.middleware("http")
    async def _log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        logger.info("request start %s %s", request.method, request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception(
                "request error %s %s after %.0fms",
                request.method,
                request.url.path,
                elapsed,
            )
            raise
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(
            "request done %s %s %d %.0fms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )
        return response

    app.include_router(health.router)
    app.include_router(stats.router)
    app.include_router(source.router)
    app.include_router(sources.router, prefix="/sources", tags=["sources"])
    app.include_router(documents.router, prefix="/documents", tags=["documents"])
    app.include_router(search.router, prefix="/search", tags=["search"])
    app.include_router(
        search.semantic_router, prefix="/semantic-search", tags=["search"]
    )
    app.include_router(manifests.router, prefix="/manifests", tags=["manifests"])
    app.include_router(ask.router, tags=["agent"])
    return app


app = create_app()

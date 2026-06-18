# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from ..shared.config import get_settings
from ..shared.logging import configure_logging
from .routers import documents, health, manifests, search, source, sources, stats


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
    return app


app = create_app()

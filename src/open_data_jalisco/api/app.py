from fastapi import FastAPI

from .. import __version__
from ..shared.config import get_settings
from ..shared.logging import configure_logging
from .routers import documents, health, manifests, search, sources


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
    app.include_router(health.router)
    app.include_router(sources.router, prefix="/sources", tags=["sources"])
    app.include_router(documents.router, prefix="/documents", tags=["documents"])
    app.include_router(search.router, prefix="/search", tags=["search"])
    app.include_router(
        search.semantic_router, prefix="/semantic-search", tags=["search"]
    )
    app.include_router(manifests.router, prefix="/manifests", tags=["manifests"])
    return app


app = create_app()

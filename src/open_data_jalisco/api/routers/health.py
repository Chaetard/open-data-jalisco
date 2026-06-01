from fastapi import APIRouter

from ... import __version__
from ...shared.config import get_settings

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "environment": settings.environment,
    }

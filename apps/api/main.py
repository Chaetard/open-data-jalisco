# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Thin process entry point for the FastAPI application.

The real implementation lives in ``open_data_jalisco.api.app``. This module
exists so the deployment surface (``apps/api/main.py``) is decoupled from the
internal package layout. Run with::

    uv run uvicorn apps.api.main:app --reload --app-dir .
"""
from __future__ import annotations

from open_data_jalisco.api.app import app, create_app

__all__ = ["app", "create_app"]


if __name__ == "__main__":
    import uvicorn

    from open_data_jalisco.shared.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "apps.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        app_dir=".",
    )

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from pathlib import Path

from fastapi import APIRouter, Depends, Query

from ...manifests import list_manifests
from ..deps import get_manifests_dir
from ..schemas import ManifestSummary

router = APIRouter()


@router.get("", response_model=list[ManifestSummary])
def get_manifests(
    source_slug: str | None = Query(default=None, description="Filter by source slug"),
    manifests_dir: Path = Depends(get_manifests_dir),
) -> list[ManifestSummary]:
    """List integrity manifests previously written under ``MANIFESTS_DIR``.

    Each item summarises one JSON manifest file produced by ``odj manifest``.
    """
    items = list_manifests(manifests_dir)
    if source_slug:
        items = [m for m in items if m.get("source_slug") == source_slug]
    return [ManifestSummary(**m) for m in items]

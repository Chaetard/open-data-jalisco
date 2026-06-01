# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from fastapi import APIRouter, Depends, HTTPException

from ...ports.repositories import SourceRepository
from ..deps import get_source_repository
from ..schemas import SourceOut, source_to_out

router = APIRouter()


@router.get("", response_model=list[SourceOut])
def list_sources(
    include_inactive: bool = False,
    repo: SourceRepository = Depends(get_source_repository),
) -> list[SourceOut]:
    items = repo.list_all() if include_inactive else repo.list_active()
    return [source_to_out(s) for s in items]


@router.get("/{slug}", response_model=SourceOut)
def get_source(
    slug: str,
    repo: SourceRepository = Depends(get_source_repository),
) -> SourceOut:
    source = repo.get_by_slug(slug)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Source not found: {slug}")
    return source_to_out(source)

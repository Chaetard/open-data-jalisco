# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Aggregate metrics endpoint for dashboard cards.

Frontends should hit this instead of enumerating /documents to compute counts:
it's one query per metric vs. paginating through thousands of rows. Numbers
match the ``odj db stats`` CLI exactly.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from ...adapters.persistence import get_session_factory
from ...adapters.persistence.models import ChunkORM, DocumentORM, SourceORM

router = APIRouter(tags=["meta"])


class StatusCount(BaseModel):
    status: str
    count: int


class SourceCount(BaseModel):
    slug: str
    count: int


class StatsResponse(BaseModel):
    documents_total: int
    documents_by_status: list[StatusCount]
    chunks_total: int
    unique_documents_by_sha256: int
    sources_total: int
    documents_by_source: list[SourceCount]


@router.get("/stats", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    sf = get_session_factory()
    with sf() as session:
        by_status_rows = session.execute(
            select(DocumentORM.processing_status, func.count())
            .where(DocumentORM.is_current.is_(True))
            .group_by(DocumentORM.processing_status)
            .order_by(DocumentORM.processing_status)
        ).all()
        docs_total = sum(n for _, n in by_status_rows)

        chunks_total = session.scalar(select(func.count()).select_from(ChunkORM)) or 0
        unique_sha = (
            session.scalar(select(func.count(func.distinct(ChunkORM.sha256)))) or 0
        )

        sources_total = session.scalar(select(func.count()).select_from(SourceORM)) or 0
        by_source_rows = session.execute(
            select(SourceORM.slug, func.count(DocumentORM.id))
            .join(DocumentORM, DocumentORM.source_id == SourceORM.id, isouter=True)
            .where(DocumentORM.is_current.is_(True))
            .group_by(SourceORM.slug)
            .order_by(SourceORM.slug)
        ).all()

    return StatsResponse(
        documents_total=docs_total,
        documents_by_status=[StatusCount(status=s, count=n) for s, n in by_status_rows],
        chunks_total=chunks_total,
        unique_documents_by_sha256=unique_sha,
        sources_total=sources_total,
        documents_by_source=[SourceCount(slug=s, count=n) for s, n in by_source_rows],
    )

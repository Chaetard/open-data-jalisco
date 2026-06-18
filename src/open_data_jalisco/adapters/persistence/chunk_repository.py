# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from collections.abc import Callable, Iterable
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...domain.chunk import Chunk
from ._mappers import chunk_to_domain, chunk_to_orm
from .models import ChunkORM

# Why: SAPUMU (and similar portals) re-publish the same PDF under multiple
# content_ids. Each copy lands as a distinct Document row (different URL, same
# sha256) and contributes the same chunks to the index. We over-fetch from the
# vector search and then collapse by sha256 so the user sees one hit per
# unique file. 5x with a floor of 50 absorbs realistic duplication without a
# window function or schema change.
_OVERFETCH_FACTOR = 5
_OVERFETCH_MIN = 50


class PostgresChunkRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._sf = session_factory

    def bulk_insert(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        with self._sf() as session:
            session.add_all([chunk_to_orm(c) for c in chunks])
            session.commit()
            return len(chunks)

    def delete_for_document(self, document_id: UUID) -> int:
        with self._sf() as session:
            result = session.execute(
                delete(ChunkORM).where(ChunkORM.document_id == document_id)
            )
            session.commit()
            return result.rowcount or 0

    def list_by_document(self, document_id: UUID) -> list[Chunk]:
        with self._sf() as session:
            rows = session.scalars(
                select(ChunkORM)
                .where(ChunkORM.document_id == document_id)
                .order_by(ChunkORM.chunk_index)
            ).all()
            return [chunk_to_domain(r) for r in rows]

    def semantic_search(
        self,
        embedding: list[float],
        *,
        limit: int = 10,
        municipality: str | None = None,
        document_type: str | None = None,
        source_id: UUID | None = None,
    ) -> list[tuple[Chunk, float]]:
        fetch_n = max(limit * _OVERFETCH_FACTOR, _OVERFETCH_MIN)
        with self._sf() as session:
            distance = ChunkORM.embedding.cosine_distance(embedding).label("distance")
            stmt = select(ChunkORM, distance).where(ChunkORM.embedding.isnot(None))
            if municipality is not None:
                stmt = stmt.where(ChunkORM.municipality == municipality)
            if document_type is not None:
                stmt = stmt.where(ChunkORM.document_type == document_type)
            if source_id is not None:
                stmt = stmt.where(ChunkORM.source_id == source_id)
            stmt = stmt.order_by(distance.asc()).limit(fetch_n)
            ranked = (
                (chunk_to_domain(row[0]), float(row[1]))
                for row in session.execute(stmt).all()
            )
            return dedupe_by_sha256(ranked, limit=limit)


def dedupe_by_sha256(
    ranked: Iterable[tuple[Chunk, float]], *, limit: int
) -> list[tuple[Chunk, float]]:
    """Keep only the best-scoring chunk per ``sha256``, up to ``limit`` hits.

    Input must already be ordered by ascending distance (best first). Order is
    preserved on the output: callers can rely on ``result[0]`` being the global
    best.
    """
    seen: set[str] = set()
    out: list[tuple[Chunk, float]] = []
    for chunk, distance in ranked:
        if chunk.sha256 in seen:
            continue
        seen.add(chunk.sha256)
        out.append((chunk, distance))
        if len(out) >= limit:
            break
    return out

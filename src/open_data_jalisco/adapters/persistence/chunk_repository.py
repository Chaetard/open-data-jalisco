# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from collections.abc import Callable, Iterable
from uuid import UUID

from sqlalchemy import ColumnElement, delete, func, literal_column, select
from sqlalchemy.orm import Session

from ...domain.chunk import Chunk
from ._mappers import chunk_to_domain, chunk_to_orm
from .models import ChunkORM, DocumentORM

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
        year: int | None = None,
    ) -> list[tuple[Chunk, float]]:
        fetch_n = max(limit * _OVERFETCH_FACTOR, _OVERFETCH_MIN)
        with self._sf() as session:
            distance = ChunkORM.embedding.cosine_distance(embedding).label("distance")
            # Join documents + is_current so superseded versions' chunks never
            # surface: re-ingesting an updated doc leaves the old version's chunks
            # behind (different sha256, so dedupe_by_sha256 won't collapse them).
            stmt = (
                select(ChunkORM, distance)
                .join(DocumentORM, DocumentORM.id == ChunkORM.document_id)
                .where(ChunkORM.embedding.isnot(None), DocumentORM.is_current.is_(True))
            )
            if municipality is not None:
                stmt = stmt.where(ChunkORM.municipality == municipality)
            if document_type is not None:
                stmt = stmt.where(ChunkORM.document_type == document_type)
            if source_id is not None:
                stmt = stmt.where(ChunkORM.source_id == source_id)
            if year is not None:
                stmt = stmt.where(ChunkORM.year == year)
            stmt = stmt.order_by(distance.asc()).limit(fetch_n)
            ranked = (
                (chunk_to_domain(row[0]), float(row[1]))
                for row in session.execute(stmt).all()
            )
            return dedupe_by_sha256(ranked, limit=limit)

    def lexical_search(
        self,
        query: str,
        *,
        limit: int = 10,
        municipality: str | None = None,
        document_type: str | None = None,
        source_id: UUID | None = None,
        year: int | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Full-text (BM25-ish) search over chunk text.

        Catches what embeddings miss: exact codes (333, 3300, FAISMUN), RFCs,
        proper names, amounts — tokens the e5 model fragments into subwords. The
        'spanish' config gives stemming + stopwords; numbers/acronyms pass
        through as literal lexemes. Returned float is ts_rank (higher = better),
        not a distance — the caller fuses it with the vector arm by rank, not by
        raw value. ``literal_column('spanish')`` (not a bind param) and the
        ``odj_unaccent`` wrapper mirror the indexed expression from init_db
        exactly so the planner can use the matching GIN index.
        """
        fetch_n = max(limit * _OVERFETCH_FACTOR, _OVERFETCH_MIN)
        with self._sf() as session:
            config: ColumnElement[str] = literal_column("'spanish'")
            # Fold accents on BOTH sides so "adjudicacion" matches "adjudicación".
            tsv = func.to_tsvector(config, func.odj_unaccent(ChunkORM.text))
            tsq = func.websearch_to_tsquery(config, func.odj_unaccent(query))
            rank = func.ts_rank(tsv, tsq).label("rank")
            # See semantic_search: only current-version chunks are searchable.
            stmt = (
                select(ChunkORM, rank)
                .join(DocumentORM, DocumentORM.id == ChunkORM.document_id)
                .where(tsv.op("@@")(tsq), DocumentORM.is_current.is_(True))
            )
            if municipality is not None:
                stmt = stmt.where(ChunkORM.municipality == municipality)
            if document_type is not None:
                stmt = stmt.where(ChunkORM.document_type == document_type)
            if source_id is not None:
                stmt = stmt.where(ChunkORM.source_id == source_id)
            if year is not None:
                stmt = stmt.where(ChunkORM.year == year)
            stmt = stmt.order_by(rank.desc()).limit(fetch_n)
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

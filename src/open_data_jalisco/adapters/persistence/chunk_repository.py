from collections.abc import Callable
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...domain.chunk import Chunk
from ._mappers import chunk_to_domain, chunk_to_orm
from .models import ChunkORM


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
        with self._sf() as session:
            distance = ChunkORM.embedding.cosine_distance(embedding).label("distance")
            stmt = select(ChunkORM, distance).where(ChunkORM.embedding.isnot(None))
            if municipality is not None:
                stmt = stmt.where(ChunkORM.municipality == municipality)
            if document_type is not None:
                stmt = stmt.where(ChunkORM.document_type == document_type)
            if source_id is not None:
                stmt = stmt.where(ChunkORM.source_id == source_id)
            stmt = stmt.order_by(distance.asc()).limit(limit)
            results: list[tuple[Chunk, float]] = []
            for row in session.execute(stmt).all():
                orm: ChunkORM = row[0]
                dist: float = float(row[1])
                results.append((chunk_to_domain(orm), dist))
            return results

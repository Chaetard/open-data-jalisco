# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Test-only fakes that satisfy the hexagonal ports without touching DB or network."""
from __future__ import annotations

from uuid import UUID, uuid4

from open_data_jalisco.domain.chunk import Chunk
from open_data_jalisco.domain.document import Document
from open_data_jalisco.domain.enums import DocumentType, ProcessingStatus
from open_data_jalisco.shared.time import utcnow


class FakeEmbedder:
    name = "fake"
    model = "fake-v1"
    dimension = 4

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3, 0.4]


class FakeChunkRepo:
    def __init__(self, chunks: list[Chunk]):
        self._chunks = chunks

    def bulk_insert(self, chunks: list[Chunk]) -> int:
        return 0

    def delete_for_document(self, document_id: UUID) -> int:
        return 0

    def list_by_document(self, document_id: UUID) -> list[Chunk]:
        return [c for c in self._chunks if c.document_id == document_id]

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
        return [(c, 0.1) for c in self._chunks[:limit]]

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
        # Naive substring match stands in for Postgres FTS so hybrid search is
        # exercisable without a DB.
        q = query.lower()
        hits = [(c, 1.0) for c in self._chunks if q in c.text.lower()]
        return hits[:limit]


class FakeDocRepo:
    def __init__(self, docs: list[Document]):
        self._docs = {d.id: d for d in docs}

    def get_by_id(self, document_id: UUID) -> Document | None:
        return self._docs.get(document_id)

    def find_by_url_and_hash(self, *a, **kw) -> Document | None:
        return None

    def find_current_by_url(self, *a, **kw) -> Document | None:
        return None

    def find_current_by_official_url(self, official_url: str) -> Document | None:
        return next(
            (d for d in self._docs.values() if d.official_url == official_url), None
        )

    def count_documents(
        self,
        *,
        municipality: str | None = None,
        year: int | None = None,
        document_type: str | None = None,
        processing_status: str | None = None,
        current_only: bool = True,
    ) -> int:
        def ok(d: Document) -> bool:
            return all(
                [
                    municipality is None or d.municipality == municipality,
                    year is None or d.year == year,
                    document_type is None or d.document_type.value == document_type,
                    processing_status is None
                    or d.processing_status.value == processing_status,
                ]
            )

        return sum(1 for d in self._docs.values() if ok(d))

    def insert_new_version(self, document: Document, supersedes: Document | None) -> Document:
        return document

    def update(self, document: Document) -> Document:
        return document

    def list_documents(self, **kwargs) -> list[Document]:
        return list(self._docs.values())

    def list_pending(
        self, limit: int = 50, *, include_failed: bool = False
    ) -> list[Document]:
        return []


def make_document(
    *,
    title: str = "Sample document",
    municipality: str = "Example",
    document_type: DocumentType = DocumentType.OTHER,
    year: int | None = 2024,
) -> Document:
    return Document(
        source_id=uuid4(),
        sha256="0" * 64,
        official_url="https://example.invalid/sample",
        mime_type="application/pdf",
        storage_path="data/raw/sample.pdf",
        file_size=1024,
        captured_at=utcnow(),
        municipality=municipality,
        document_type=document_type,
        title=title,
        year=year,
        processing_status=ProcessingStatus.INDEXED,
    )


def make_chunk(doc: Document, *, text: str = "Sample chunk text", index: int = 0) -> Chunk:
    return Chunk(
        document_id=doc.id,
        source_id=doc.source_id,
        sha256=doc.sha256,
        chunk_index=index,
        text=text,
        char_count=len(text),
        captured_at=doc.captured_at,
        municipality=doc.municipality,
        document_type=doc.document_type,
        year=doc.year,
    )

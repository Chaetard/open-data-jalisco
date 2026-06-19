# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from typing import Protocol
from uuid import UUID

from ..domain.chunk import Chunk
from ..domain.document import Document
from ..domain.source import Source


class SourceRepository(Protocol):
    def upsert(self, source: Source) -> Source: ...
    def get_by_slug(self, slug: str) -> Source | None: ...
    def get_by_id(self, source_id: UUID) -> Source | None: ...
    def list_active(self) -> list[Source]: ...
    def list_all(self) -> list[Source]: ...


class DocumentRepository(Protocol):
    def get_by_id(self, document_id: UUID) -> Document | None: ...

    def find_by_url_and_hash(
        self, source_id: UUID, official_url: str, sha256: str
    ) -> Document | None: ...

    def find_current_by_url(
        self, source_id: UUID, official_url: str
    ) -> Document | None: ...

    def insert_new_version(
        self, document: Document, supersedes: Document | None
    ) -> Document: ...

    def update(self, document: Document) -> Document: ...

    def list_documents(
        self,
        *,
        source_id: UUID | None = None,
        municipality: str | None = None,
        document_type: str | None = None,
        year: int | None = None,
        current_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]: ...

    def list_pending(
        self, limit: int = 50, *, include_failed: bool = False
    ) -> list[Document]: ...


class ChunkRepository(Protocol):
    def bulk_insert(self, chunks: list[Chunk]) -> int: ...
    def delete_for_document(self, document_id: UUID) -> int: ...
    def list_by_document(self, document_id: UUID) -> list[Chunk]: ...

    def semantic_search(
        self,
        embedding: list[float],
        *,
        limit: int = 10,
        municipality: str | None = None,
        document_type: str | None = None,
        source_id: UUID | None = None,
    ) -> list[tuple[Chunk, float]]:
        ...

    def lexical_search(
        self,
        query: str,
        *,
        limit: int = 10,
        municipality: str | None = None,
        document_type: str | None = None,
        source_id: UUID | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Full-text search over chunk text. Float is ts_rank (higher better)."""
        ...

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ..domain.chunk import Chunk
from ..domain.document import Document
from ..domain.source import Source


class SourceOut(BaseModel):
    id: UUID
    slug: str
    name: str
    kind: str
    municipality: str
    official_url: str
    description: str | None
    is_active: bool


class DocumentOut(BaseModel):
    id: UUID
    source_id: UUID
    sha256: str
    title: str | None
    document_type: str
    municipality: str
    year: int | None
    official_url: str
    captured_url: str | None
    captured_at: datetime
    mime_type: str
    storage_path: str
    file_size: int
    processing_status: str
    needs_ocr: bool
    version: int
    is_current: bool
    superseded_by: UUID | None


class ChunkOut(BaseModel):
    id: UUID
    document_id: UUID
    source_id: UUID
    sha256: str
    chunk_index: int
    text: str
    char_count: int
    page_start: int | None
    page_end: int | None
    section_title: str | None
    document_type: str
    municipality: str
    year: int | None


class SearchHit(BaseModel):
    score: float
    chunk: ChunkOut
    document: DocumentOut


class SearchResponse(BaseModel):
    query: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    hits: list[SearchHit]


class SearchRequest(BaseModel):
    q: str = Field(min_length=2, description="Free-text query")
    limit: int = Field(default=10, ge=1, le=50)
    municipality: str | None = None
    document_type: str | None = None
    source_id: UUID | None = None


class ManifestSummary(BaseModel):
    filename: str
    source_slug: str
    municipality: str | None = None
    generated_at: str | None = None
    document_count: int | None = None
    pipeline_version: str | None = None


def source_to_out(s: Source) -> SourceOut:
    return SourceOut(
        id=s.id,
        slug=s.slug,
        name=s.name,
        kind=s.kind.value,
        municipality=s.municipality,
        official_url=s.official_url,
        description=s.description,
        is_active=s.is_active,
    )


def document_to_out(d: Document) -> DocumentOut:
    return DocumentOut(
        id=d.id,
        source_id=d.source_id,
        sha256=d.sha256,
        title=d.title,
        document_type=d.document_type.value,
        municipality=d.municipality,
        year=d.year,
        official_url=d.official_url,
        captured_url=d.captured_url,
        captured_at=d.captured_at,
        mime_type=d.mime_type,
        storage_path=d.storage_path,
        file_size=d.file_size,
        processing_status=d.processing_status.value,
        needs_ocr=d.needs_ocr,
        version=d.version,
        is_current=d.is_current,
        superseded_by=d.superseded_by,
    )


def chunk_to_out(c: Chunk) -> ChunkOut:
    return ChunkOut(
        id=c.id,
        document_id=c.document_id,
        source_id=c.source_id,
        sha256=c.sha256,
        chunk_index=c.chunk_index,
        text=c.text,
        char_count=c.char_count,
        page_start=c.page_start,
        page_end=c.page_end,
        section_title=c.section_title,
        document_type=c.document_type.value,
        municipality=c.municipality,
        year=c.year,
    )

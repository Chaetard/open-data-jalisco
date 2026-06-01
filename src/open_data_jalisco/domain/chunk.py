from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from ..shared.time import utcnow
from .enums import DocumentType


@dataclass
class Chunk:
    document_id: UUID
    source_id: UUID
    sha256: str
    chunk_index: int
    text: str
    char_count: int
    captured_at: datetime
    municipality: str
    document_type: DocumentType = DocumentType.UNKNOWN
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None
    year: int | None = None
    metadata: dict[str, Any] | None = None
    embedding: list[float] | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)

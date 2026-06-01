from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from ..shared.time import utcnow
from .enums import DocumentType, ProcessingStatus


@dataclass
class Document:
    source_id: UUID
    sha256: str
    official_url: str
    mime_type: str
    storage_path: str
    file_size: int
    captured_at: datetime
    municipality: str
    document_type: DocumentType = DocumentType.UNKNOWN
    title: str | None = None
    year: int | None = None
    captured_url: str | None = None
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    needs_ocr: bool = False
    version: int = 1
    is_current: bool = True
    superseded_by: UUID | None = None
    extraction_error: str | None = None
    metadata: dict[str, Any] | None = None
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

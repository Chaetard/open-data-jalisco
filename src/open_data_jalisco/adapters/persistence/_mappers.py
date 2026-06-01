from ...domain.chunk import Chunk
from ...domain.document import Document
from ...domain.enums import DocumentType, ProcessingStatus, SourceKind
from ...domain.source import Source
from .models import ChunkORM, DocumentORM, SourceORM


def source_to_orm(s: Source) -> SourceORM:
    return SourceORM(
        id=s.id,
        slug=s.slug,
        name=s.name,
        kind=s.kind.value,
        municipality=s.municipality,
        official_url=s.official_url,
        description=s.description,
        metadata_json=s.metadata,
        is_active=s.is_active,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


def source_to_domain(o: SourceORM) -> Source:
    return Source(
        id=o.id,
        slug=o.slug,
        name=o.name,
        kind=SourceKind(o.kind),
        municipality=o.municipality,
        official_url=o.official_url,
        description=o.description,
        metadata=o.metadata_json,
        is_active=o.is_active,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )


def document_to_orm(d: Document) -> DocumentORM:
    return DocumentORM(
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
        extraction_error=d.extraction_error,
        metadata_json=d.metadata,
        created_at=d.created_at,
        updated_at=d.updated_at,
    )


def document_to_domain(o: DocumentORM) -> Document:
    return Document(
        id=o.id,
        source_id=o.source_id,
        sha256=o.sha256,
        title=o.title,
        document_type=DocumentType(o.document_type),
        municipality=o.municipality,
        year=o.year,
        official_url=o.official_url,
        captured_url=o.captured_url,
        captured_at=o.captured_at,
        mime_type=o.mime_type,
        storage_path=o.storage_path,
        file_size=o.file_size,
        processing_status=ProcessingStatus(o.processing_status),
        needs_ocr=o.needs_ocr,
        version=o.version,
        is_current=o.is_current,
        superseded_by=o.superseded_by,
        extraction_error=o.extraction_error,
        metadata=o.metadata_json,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )


def chunk_to_orm(c: Chunk) -> ChunkORM:
    return ChunkORM(
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
        captured_at=c.captured_at,
        metadata_json=c.metadata,
        embedding=c.embedding,
        embedding_provider=c.embedding_provider,
        embedding_model=c.embedding_model,
        created_at=c.created_at,
    )


def chunk_to_domain(o: ChunkORM) -> Chunk:
    return Chunk(
        id=o.id,
        document_id=o.document_id,
        source_id=o.source_id,
        sha256=o.sha256,
        chunk_index=o.chunk_index,
        text=o.text,
        char_count=o.char_count,
        page_start=o.page_start,
        page_end=o.page_end,
        section_title=o.section_title,
        document_type=DocumentType(o.document_type),
        municipality=o.municipality,
        year=o.year,
        captured_at=o.captured_at,
        metadata=o.metadata_json,
        embedding=list(o.embedding) if o.embedding is not None else None,
        embedding_provider=o.embedding_provider,
        embedding_model=o.embedding_model,
        created_at=o.created_at,
    )

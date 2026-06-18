# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from dataclasses import dataclass, field
from pathlib import Path

from ..adapters.extraction import ExtractorRegistry
from ..adapters.extraction.registry import UnsupportedFormatError
from ..domain.chunk import Chunk
from ..domain.document import Document
from ..domain.enums import ProcessingStatus
from ..ports.chunker import Chunker
from ..ports.embedding_provider import EmbeddingProvider
from ..ports.raw_storage import RawStorage
from ..ports.repositories import ChunkRepository, DocumentRepository
from ..shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessingResult:
    seen: int = 0
    indexed: int = 0
    needs_ocr: int = 0
    no_text: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


class ProcessDocumentsUseCase:
    def __init__(
        self,
        *,
        document_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        raw_storage: RawStorage,
        extractors: ExtractorRegistry,
        chunker: Chunker,
        embedder: EmbeddingProvider,
    ):
        self._doc_repo = document_repo
        self._chunk_repo = chunk_repo
        self._raw = raw_storage
        self._extractors = extractors
        self._chunker = chunker
        self._embedder = embedder

    def execute(
        self, *, limit: int = 50, retry_failed: bool = False
    ) -> ProcessingResult:
        pending = self._doc_repo.list_pending(
            limit=limit, include_failed=retry_failed
        )
        result = ProcessingResult()
        for doc in pending:
            result.seen += 1
            try:
                self._process_one(doc, result)
            except Exception as e:
                logger.exception("processing.failed document_id=%s", doc.id)
                doc.processing_status = ProcessingStatus.FAILED
                doc.extraction_error = repr(e)[:1000]
                self._doc_repo.update(doc)
                result.failed += 1
                result.errors.append(f"{doc.id}: {e!r}")
        logger.info(
            "processing.done seen=%d indexed=%d needs_ocr=%d no_text=%d failed=%d",
            result.seen,
            result.indexed,
            result.needs_ocr,
            result.no_text,
            result.failed,
        )
        return result

    def _process_one(self, doc: Document, result: ProcessingResult) -> None:
        path: Path = self._raw.open(doc.storage_path)
        if not path.exists():
            raise FileNotFoundError(f"Raw file missing: {path}")
        extension = _derive_extension(doc.storage_path)
        try:
            extracted = self._extractors.extract(path, doc.mime_type, extension)
        except UnsupportedFormatError as e:
            doc.processing_status = ProcessingStatus.FAILED
            doc.extraction_error = str(e)
            self._doc_repo.update(doc)
            result.failed += 1
            result.errors.append(f"{doc.id}: {e}")
            return

        if extracted.needs_ocr:
            doc.needs_ocr = True
            doc.processing_status = ProcessingStatus.NEEDS_OCR
            self._doc_repo.update(doc)
            result.needs_ocr += 1
            return

        candidates = self._chunker.chunk(extracted, document_type=doc.document_type.value)
        if not candidates:
            doc.processing_status = ProcessingStatus.EXTRACTED
            doc.extraction_error = "no_chunks_produced"
            self._doc_repo.update(doc)
            result.no_text += 1
            return

        self._chunk_repo.delete_for_document(doc.id)
        embed_inputs = [_compose_embedding_input(doc, c) for c in candidates]
        vectors = self._embedder.embed(embed_inputs)
        chunks = [
            Chunk(
                document_id=doc.id,
                source_id=doc.source_id,
                sha256=doc.sha256,
                chunk_index=c.chunk_index,
                text=c.text,
                char_count=len(c.text),
                page_start=c.page_start,
                page_end=c.page_end,
                section_title=c.section_title,
                document_type=doc.document_type,
                municipality=doc.municipality,
                year=doc.year,
                captured_at=doc.captured_at,
                embedding=vec,
                embedding_provider=self._embedder.name,
                embedding_model=self._embedder.model,
            )
            for c, vec in zip(candidates, vectors, strict=True)
        ]
        self._chunk_repo.bulk_insert(chunks)
        doc.processing_status = ProcessingStatus.INDEXED
        doc.extraction_error = None
        self._doc_repo.update(doc)
        result.indexed += 1


def _derive_extension(storage_path: str) -> str:
    if "." in storage_path:
        return storage_path.rsplit(".", 1)[-1].lower()
    return ""


def _compose_embedding_input(doc: Document, candidate) -> str:
    """Build the text that goes into the embedder for a chunk.

    Why: a chunk's body may not mention the entity the user is searching for
    (e.g. the contracting company name lives in the document title but not in
    every page of the body). Prepending the document title — and the chunk's
    section heading if available — gives every chunk a chance to match those
    queries without changing the text persisted to the database.
    """
    parts: list[str] = []
    if doc.title:
        parts.append(doc.title.strip())
    if candidate.section_title:
        parts.append(candidate.section_title.strip())
    parts.append(candidate.text)
    return "\n\n".join(parts)

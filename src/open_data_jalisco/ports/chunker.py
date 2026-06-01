from dataclasses import dataclass
from typing import Protocol

from .text_extractor import ExtractedDocument


@dataclass
class ChunkCandidate:
    chunk_index: int
    text: str
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None


class Chunker(Protocol):
    def chunk(
        self,
        extracted: ExtractedDocument,
        *,
        document_type: str | None = None,
    ) -> list[ChunkCandidate]:
        ...

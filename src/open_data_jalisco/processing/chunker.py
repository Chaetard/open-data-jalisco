import re

from ..ports.chunker import ChunkCandidate
from ..ports.text_extractor import ExtractedDocument
from ..shared.config import get_settings

_HEADING_PATTERNS = [
    re.compile(r"^\s*(ART[ÍI]CULO\s+[\wºª°\-\.]+)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(CAP[ÍI]TULO\s+[\wºª°\-]+)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(T[ÍI]TULO\s+[\wºª°\-]+)", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^\s*(SECCI[ÓO]N\s+[\wºª°\-]+)", re.IGNORECASE | re.MULTILINE),
]


def _detect_section_title(text: str) -> str | None:
    earliest: tuple[int, str] | None = None
    for pat in _HEADING_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        line_end = text.find("\n", m.start())
        end = line_end if line_end != -1 else min(len(text), m.start() + 120)
        snippet = text[m.start() : end].strip()
        if earliest is None or m.start() < earliest[0]:
            earliest = (m.start(), snippet)
    return earliest[1] if earliest else None


def _split_text_with_overlap(text: str, *, max_chars: int, overlap: int) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []
    parts: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        if end < n:
            ws = text.rfind(" ", start, end)
            if ws > start + max_chars // 2:
                end = ws
        chunk = text[start:end].strip()
        if chunk:
            parts.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return parts


class StructureAwareChunker:
    """Page-aware chunker with paragraph fallback.

    - If the extracted document has page boundaries (PDFs), build buckets that
      respect those boundaries; small pages are merged with neighbors so we
      don't emit micro-chunks. Within each bucket, oversized text is split with
      character overlap.
    - If there are no pages (HTML/plaintext), fall back to a paragraph-aware
      sliding window with overlap.
    """

    def __init__(self, *, max_chars: int = 1800, overlap: int = 200, min_chars: int = 120):
        if overlap >= max_chars:
            raise ValueError("overlap must be smaller than max_chars")
        self._max = max_chars
        self._overlap = overlap
        self._min = min_chars

    def chunk(
        self,
        extracted: ExtractedDocument,
        *,
        document_type: str | None = None,
    ) -> list[ChunkCandidate]:
        if extracted.pages:
            return self._chunk_paginated(extracted)
        return self._chunk_flat(extracted.full_text)

    def _chunk_paginated(self, extracted: ExtractedDocument) -> list[ChunkCandidate]:
        buckets: list[tuple[int, int, str]] = []
        pending_pages: list[int] = []
        pending_text: list[str] = []
        pending_len = 0

        for page in extracted.pages:
            t = page.text.strip()
            if not t:
                continue
            pending_pages.append(page.page_number)
            pending_text.append(t)
            pending_len += len(t) + 2
            if pending_len >= self._min:
                buckets.append(
                    (pending_pages[0], pending_pages[-1], "\n\n".join(pending_text))
                )
                pending_pages, pending_text, pending_len = [], [], 0

        if pending_pages:
            tail_text = "\n\n".join(pending_text)
            if buckets and pending_len < self._min:
                last_start, _, last_text = buckets[-1]
                buckets[-1] = (last_start, pending_pages[-1], f"{last_text}\n\n{tail_text}")
            else:
                buckets.append((pending_pages[0], pending_pages[-1], tail_text))

        candidates: list[ChunkCandidate] = []
        idx = 0
        for ps, pe, text in buckets:
            section_title = _detect_section_title(text)
            for sub in _split_text_with_overlap(
                text, max_chars=self._max, overlap=self._overlap
            ):
                candidates.append(
                    ChunkCandidate(
                        chunk_index=idx,
                        text=sub,
                        page_start=ps,
                        page_end=pe,
                        section_title=section_title,
                    )
                )
                idx += 1
        return candidates

    def _chunk_flat(self, full_text: str) -> list[ChunkCandidate]:
        full_text = full_text.strip()
        if not full_text:
            return []
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", full_text) if p.strip()]

        buckets: list[str] = []
        current: list[str] = []
        current_len = 0
        for p in paragraphs:
            if current and current_len + len(p) > self._max:
                buckets.append("\n\n".join(current))
                tail = "\n\n".join(current)[-self._overlap :] if self._overlap > 0 else ""
                current = [tail, p] if tail else [p]
                current_len = len(tail) + len(p)
            else:
                current.append(p)
                current_len += len(p) + 2
        if current:
            buckets.append("\n\n".join(current))

        candidates: list[ChunkCandidate] = []
        for idx, text in enumerate(buckets):
            candidates.append(
                ChunkCandidate(
                    chunk_index=idx,
                    text=text,
                    section_title=_detect_section_title(text),
                )
            )
        return candidates


def build_chunker() -> StructureAwareChunker:
    s = get_settings()
    return StructureAwareChunker(
        max_chars=s.chunk_max_chars,
        overlap=s.chunk_overlap_chars,
        min_chars=s.chunk_min_chars,
    )

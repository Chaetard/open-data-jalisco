# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ...ports.text_extractor import ExtractedDocument, ExtractedPage
from ...shared.logging import get_logger

logger = get_logger(__name__)

_PDF_MIME = {"application/pdf", "application/x-pdf"}
_PDF_EXTENSIONS = {"pdf"}

# Drop every C0 control char except TAB/LF/CR. The critical one is NUL (0x00),
# which Postgres TEXT columns reject outright (psycopg.DataError). The rest of
# the 0x01–0x1F range shows up in malformed PDFs as raw byte sequences from
# font-encoding tables pypdf couldn't decode (e.g. /SymbolSetEncoding) — it's
# not real document content, just garbage that poisons the search index.
_CONTROL_CHARS = "".join(chr(i) for i in range(32) if i not in (9, 10, 13))
_STRIP_TABLE = str.maketrans("", "", _CONTROL_CHARS)
# Threshold below which page text is considered unsalvageable garbage.
_MIN_PRINTABLE_RATIO = 0.5


class PdfTextExtractor:
    def can_handle(self, mime_type: str, extension: str) -> bool:
        return mime_type.lower() in _PDF_MIME or extension.lower().lstrip(".") in _PDF_EXTENSIONS

    def extract(self, path: Path) -> ExtractedDocument:
        try:
            reader = PdfReader(str(path))
        except PdfReadError as e:
            logger.warning("pdf.extract.read_error path=%s err=%s", path, e)
            return ExtractedDocument(full_text="", pages=[], needs_ocr=True, metadata={"error": str(e)})

        pages: list[ExtractedPage] = []
        total_chars = 0
        garbage_pages = 0
        for idx, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as e:
                logger.warning("pdf.extract.page_error path=%s page=%d err=%s", path, idx, e)
                text = ""
            text = _sanitize(text)
            if _is_garbage(text):
                garbage_pages += 1
                logger.warning(
                    "pdf.extract.garbage_page path=%s page=%d printable_ratio_below=%.2f",
                    path, idx, _MIN_PRINTABLE_RATIO,
                )
                text = ""
            text = text.strip()
            pages.append(ExtractedPage(page_number=idx, text=text))
            total_chars += len(text)

        full_text = "\n\n".join(p.text for p in pages if p.text)
        # Heuristic: PDFs with no extractable text are likely image-only and need OCR.
        needs_ocr = total_chars == 0 and len(pages) > 0
        return ExtractedDocument(
            full_text=full_text,
            pages=pages,
            needs_ocr=needs_ocr,
            metadata={
                "page_count": len(pages),
                "garbage_pages_dropped": garbage_pages,
            },
        )


def _sanitize(text: str) -> str:
    """Remove NUL and other C0 control chars (keep TAB/LF/CR)."""
    if not text:
        return text
    return text.translate(_STRIP_TABLE)


def _is_garbage(text: str) -> bool:
    """True if the page is mostly non-printable junk (failed encoding table)."""
    if not text:
        return False
    printable = sum(1 for c in text if c.isprintable() or c in "\n\t\r")
    return printable / len(text) < _MIN_PRINTABLE_RATIO

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
        for idx, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception as e:
                logger.warning("pdf.extract.page_error path=%s page=%d err=%s", path, idx, e)
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
            metadata={"page_count": len(pages)},
        )

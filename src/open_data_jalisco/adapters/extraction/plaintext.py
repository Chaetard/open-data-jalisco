from pathlib import Path

from ...ports.text_extractor import ExtractedDocument, ExtractedPage

_TEXT_MIME = {"text/plain", "text/markdown", "text/csv"}
_TEXT_EXTENSIONS = {"txt", "md", "csv", "tsv"}


class PlainTextExtractor:
    def can_handle(self, mime_type: str, extension: str) -> bool:
        return mime_type.lower() in _TEXT_MIME or extension.lower().lstrip(".") in _TEXT_EXTENSIONS

    def extract(self, path: Path) -> ExtractedDocument:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        pages = [ExtractedPage(page_number=1, text=text)] if text else []
        return ExtractedDocument(full_text=text, pages=pages, needs_ocr=False)

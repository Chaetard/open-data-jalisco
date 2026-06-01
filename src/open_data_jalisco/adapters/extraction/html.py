# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from pathlib import Path

import trafilatura
from bs4 import BeautifulSoup

from ...ports.text_extractor import ExtractedDocument, ExtractedPage

_HTML_MIME = {"text/html", "application/xhtml+xml"}
_HTML_EXTENSIONS = {"html", "htm", "xhtml"}


class HtmlTextExtractor:
    def can_handle(self, mime_type: str, extension: str) -> bool:
        return mime_type.lower() in _HTML_MIME or extension.lower().lstrip(".") in _HTML_EXTENSIONS

    def extract(self, path: Path) -> ExtractedDocument:
        raw = path.read_bytes()
        text = trafilatura.extract(
            raw.decode("utf-8", errors="replace"),
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        ) or ""

        soup = BeautifulSoup(raw, "lxml")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        sections = _extract_sections(soup)
        pages = [ExtractedPage(page_number=1, text=text.strip())] if text.strip() else []

        return ExtractedDocument(
            full_text=text.strip(),
            pages=pages,
            needs_ocr=False,
            metadata={
                "title": title,
                "sections": sections,
            },
        )


def _extract_sections(soup: BeautifulSoup) -> list[dict]:
    sections: list[dict] = []
    for heading in soup.find_all(["h1", "h2", "h3"]):
        text = heading.get_text(strip=True)
        if text:
            sections.append({"level": heading.name, "title": text})
    return sections

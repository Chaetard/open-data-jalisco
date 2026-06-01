# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from pathlib import Path

from ...ports.text_extractor import ExtractedDocument, TextExtractor
from .html import HtmlTextExtractor
from .pdf import PdfTextExtractor
from .plaintext import PlainTextExtractor
from .xlsx import XlsxTextExtractor


class ExtractorRegistry:
    def __init__(self, extractors: list[TextExtractor]):
        self._extractors = extractors

    def find(self, mime_type: str, extension: str) -> TextExtractor | None:
        for extractor in self._extractors:
            if extractor.can_handle(mime_type, extension):
                return extractor
        return None

    def extract(self, path: Path, mime_type: str, extension: str) -> ExtractedDocument:
        extractor = self.find(mime_type, extension)
        if extractor is None:
            raise UnsupportedFormatError(
                f"No extractor for mime={mime_type!r} ext={extension!r}"
            )
        return extractor.extract(path)


class UnsupportedFormatError(Exception):
    pass


def build_default_registry() -> ExtractorRegistry:
    return ExtractorRegistry(
        [
            PdfTextExtractor(),
            XlsxTextExtractor(),
            HtmlTextExtractor(),
            PlainTextExtractor(),
        ]
    )

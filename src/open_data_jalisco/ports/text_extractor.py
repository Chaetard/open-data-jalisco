# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class ExtractedPage:
    page_number: int
    text: str


@dataclass
class ExtractedDocument:
    full_text: str
    pages: list[ExtractedPage] = field(default_factory=list)
    needs_ocr: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class TextExtractor(Protocol):
    def can_handle(self, mime_type: str, extension: str) -> bool:
        ...

    def extract(self, path: Path) -> ExtractedDocument:
        ...

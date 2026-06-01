# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from datetime import datetime
from pathlib import Path
from typing import Protocol


class RawStorage(Protocol):
    """Content-addressed sink for raw documents. Files are immutable once stored."""

    def store(
        self,
        *,
        content: bytes,
        sha256: str,
        source_slug: str,
        captured_at: datetime,
        extension: str,
    ) -> str:
        ...

    def open(self, storage_path: str) -> Path:
        ...

    def exists(self, storage_path: str) -> bool:
        ...

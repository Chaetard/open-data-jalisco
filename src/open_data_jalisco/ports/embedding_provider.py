# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from typing import Protocol


class EmbeddingProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts as passages/documents (for indexing)."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single text as a search query.

        Some retrieval models (e.g. the E5 family) require different
        instruction prefixes for queries vs. passages. Providers that don't
        distinguish should return the same vector as ``embed([text])[0]``.
        """
        ...

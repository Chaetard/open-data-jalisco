# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from ...ports.embedding_provider import EmbeddingProvider
from ...shared.config import get_settings
from .dummy import DummyEmbeddingProvider


def build_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "dummy":
        return DummyEmbeddingProvider(
            dimension=settings.embedding_dimension,
            model=settings.embedding_model,
        )
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")


__all__ = ["DummyEmbeddingProvider", "build_embedding_provider"]

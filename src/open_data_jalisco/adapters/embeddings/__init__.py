# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from ...ports.embedding_provider import EmbeddingProvider
from ...shared.config import get_settings
from .dummy import DummyEmbeddingProvider
from .local_st import LocalSentenceTransformerEmbedder


def build_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.embedding_provider == "dummy":
        return DummyEmbeddingProvider(
            dimension=settings.embedding_dimension,
            model=settings.embedding_model,
        )
    if settings.embedding_provider == "local_st":
        return LocalSentenceTransformerEmbedder(
            model_name=settings.embedding_model,
            device=settings.embedding_device,
        )
    raise ValueError(f"Unknown embedding provider: {settings.embedding_provider}")


__all__ = [
    "DummyEmbeddingProvider",
    "LocalSentenceTransformerEmbedder",
    "build_embedding_provider",
]

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from ...ports.reranker import Reranker
from ...shared.config import get_settings
from .cross_encoder import CrossEncoderReranker


def build_reranker() -> Reranker | None:
    """Build the configured reranker, or ``None`` when disabled.

    ``None`` (provider ``"none"``, the default) means the search path skips
    reranking entirely — no model load, no latency, behaviour identical to
    before this feature existed.
    """
    settings = get_settings()
    if settings.rerank_provider == "none":
        return None
    if settings.rerank_provider == "cross_encoder":
        return CrossEncoderReranker(
            model_name=settings.rerank_model,
            device=settings.rerank_device,
        )
    raise ValueError(f"Unknown rerank provider: {settings.rerank_provider}")


__all__ = ["CrossEncoderReranker", "build_reranker"]

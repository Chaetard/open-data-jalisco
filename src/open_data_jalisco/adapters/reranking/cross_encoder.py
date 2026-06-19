# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Cross-encoder reranker via sentence-transformers.

A bi-encoder (the E5 embedder) scores query and passage independently, so it
washes out fine distinctions — on this corpus everything finance-related lands
in a flat 0.88-0.90 band and the *state* budget outranks the municipal one. A
cross-encoder reads ``(query, passage)`` jointly and discriminates far better;
used as a second stage over the vector top-N it restores a wide, trustworthy
score gap.

Default model ``cross-encoder/mmarco-mMiniLMv2-L12-H384-v1``: multilingual
(trained on mMARCO incl. Spanish), ~470 MB, CPU-friendly. Reuses the same
``local-embed`` optional dependency as the embedder (``CrossEncoder`` ships with
sentence-transformers) — no extra dependency.

Loaded lazily on first call and reused afterwards.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder


class CrossEncoderReranker:
    def __init__(
        self,
        *,
        model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
        device: str = "cpu",
        batch_size: int = 32,
        max_length: int = 512,
    ):
        self._model_name = model_name
        self._device = device
        self._batch_size = batch_size
        self._max_length = max_length
        self._model: CrossEncoder | None = None

    @property
    def name(self) -> str:
        return "cross_encoder"

    @property
    def model(self) -> str:
        return self._model_name

    def rerank(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        self._load()
        assert self._model is not None
        scores = self._model.predict(
            [(query, p) for p in passages],
            batch_size=self._batch_size,
            show_progress_bar=False,
        )
        return [float(s) for s in scores]

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is not installed. Run "
                "`uv sync --extra local-embed` to install the reranker."
            ) from e
        self._model = CrossEncoder(
            self._model_name, device=self._device, max_length=self._max_length
        )

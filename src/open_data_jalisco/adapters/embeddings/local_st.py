# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Local Sentence-Transformers embedding provider.

Runs entirely offline (after the first model download) on CPU or GPU.
Default model: ``intfloat/multilingual-e5-small`` — 384-dim, multilingual
including Spanish, ~470 MB download, CPU-friendly. Matches the existing
``vector(384)`` pgvector schema, so switching from ``dummy`` does NOT
require a database migration.

E5 family quirk
---------------
E5 retrievers expect instruction prefixes:

- queries:  ``"query: <text>"``
- passages: ``"passage: <text>"``

We apply them automatically when the configured model name starts with
``intfloat/`` (the namespace of the E5 family). Other models receive the
text unmodified.

The model is loaded lazily on first call and reused on subsequent calls.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


_E5_PASSAGE_PREFIX = "passage: "
_E5_QUERY_PREFIX = "query: "


def _needs_e5_prefix(model_name: str) -> bool:
    # Covers intfloat/multilingual-e5-{small,base,large} and the English e5 variants.
    return model_name.startswith("intfloat/") and "e5" in model_name.lower()


class LocalSentenceTransformerEmbedder:
    """EmbeddingProvider implementation backed by sentence-transformers.

    Requires the ``local-embed`` optional dependency group:
        ``uv sync --extra local-embed``
    """

    def __init__(
        self,
        *,
        model_name: str = "intfloat/multilingual-e5-small",
        device: str = "cpu",
        normalize: bool = True,
        batch_size: int = 32,
    ):
        self._model_name = model_name
        self._device = device
        self._normalize = normalize
        self._batch_size = batch_size
        self._uses_e5 = _needs_e5_prefix(model_name)
        self._model: SentenceTransformer | None = None
        self._dimension: int | None = None

    @property
    def name(self) -> str:
        return "local_st"

    @property
    def model(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        if self._dimension is None:
            self._load()
        assert self._dimension is not None
        return self._dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        prepared = [self._prepare_passage(t) for t in texts]
        return self._encode(prepared)

    def embed_query(self, text: str) -> list[float]:
        prepared = self._prepare_query(text)
        [vec] = self._encode([prepared])
        return vec

    def _prepare_passage(self, text: str) -> str:
        return f"{_E5_PASSAGE_PREFIX}{text}" if self._uses_e5 else text

    def _prepare_query(self, text: str) -> str:
        return f"{_E5_QUERY_PREFIX}{text}" if self._uses_e5 else text

    def _encode(self, texts: list[str]) -> list[list[float]]:
        self._load()
        assert self._model is not None
        vectors = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [vec.tolist() for vec in vectors]

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "sentence-transformers is not installed. Run "
                "`uv sync --extra local-embed` to install the local embedder."
            ) from e
        self._model = SentenceTransformer(self._model_name, device=self._device)
        self._dimension = int(self._model.get_sentence_embedding_dimension())

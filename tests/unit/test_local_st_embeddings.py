# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Unit tests for LocalSentenceTransformerEmbedder.

We mock ``sentence_transformers.SentenceTransformer`` to avoid downloading
~470 MB of weights in CI. The tests focus on the adapter's contract:

- The E5 ``query: `` / ``passage: `` prefixes are applied when the configured
  model is part of the ``intfloat/`` E5 family.
- Non-E5 models receive the raw text unmodified.
- Empty input is handled without invoking the model.
- ``dimension`` is reported from the underlying model.
- ``embed_query`` returns a flat vector (not a list-of-list).
"""
from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from typing import Any, ClassVar

import pytest

from open_data_jalisco.adapters.embeddings.local_st import (
    LocalSentenceTransformerEmbedder,
)


class _FakeNumpyVector:
    """Stand-in for a numpy row that supports ``.tolist()``."""

    def __init__(self, values: list[float]):
        self._values = values

    def tolist(self) -> list[float]:
        return list(self._values)


class _FakeSentenceTransformer:
    """Records ``encode`` calls so tests can assert on the inputs received."""

    last_instance: ClassVar[_FakeSentenceTransformer | None] = None

    def __init__(self, model_name: str, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.encoded_calls: list[list[str]] = []
        self.encoded_kwargs: list[dict[str, Any]] = []
        type(self).last_instance = self

    def get_sentence_embedding_dimension(self) -> int:
        return 384

    def encode(self, texts: list[str], **kwargs: Any) -> list[_FakeNumpyVector]:
        self.encoded_calls.append(list(texts))
        self.encoded_kwargs.append(dict(kwargs))
        return [_FakeNumpyVector([0.1] * 384) for _ in texts]


@pytest.fixture
def fake_sentence_transformers(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Inject a fake ``sentence_transformers`` module into ``sys.modules``."""
    module = types.ModuleType("sentence_transformers")
    module.SentenceTransformer = _FakeSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    _FakeSentenceTransformer.last_instance = None
    yield


def test_e5_model_applies_passage_prefix_on_embed(fake_sentence_transformers: None):
    emb = LocalSentenceTransformerEmbedder(model_name="intfloat/multilingual-e5-small")
    vectors = emb.embed(["hola mundo", "segundo texto"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert _FakeSentenceTransformer.last_instance is not None
    calls = _FakeSentenceTransformer.last_instance.encoded_calls
    assert calls == [["passage: hola mundo", "passage: segundo texto"]]


def test_e5_model_applies_query_prefix_on_embed_query(fake_sentence_transformers: None):
    emb = LocalSentenceTransformerEmbedder(model_name="intfloat/multilingual-e5-small")
    vec = emb.embed_query("contrato sapumu")

    assert isinstance(vec, list)
    assert len(vec) == 384
    assert _FakeSentenceTransformer.last_instance is not None
    assert _FakeSentenceTransformer.last_instance.encoded_calls == [
        ["query: contrato sapumu"]
    ]


def test_non_e5_model_receives_raw_text(fake_sentence_transformers: None):
    emb = LocalSentenceTransformerEmbedder(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    emb.embed(["hola"])
    emb.embed_query("hola")

    assert _FakeSentenceTransformer.last_instance is not None
    calls = _FakeSentenceTransformer.last_instance.encoded_calls
    assert calls == [["hola"], ["hola"]]


def test_embed_empty_list_does_not_load_model(fake_sentence_transformers: None):
    emb = LocalSentenceTransformerEmbedder(model_name="intfloat/multilingual-e5-small")
    out = emb.embed([])

    assert out == []
    assert _FakeSentenceTransformer.last_instance is None


def test_dimension_reported_from_model(fake_sentence_transformers: None):
    emb = LocalSentenceTransformerEmbedder(model_name="intfloat/multilingual-e5-small")
    assert emb.dimension == 384


def test_provider_metadata_is_stable(fake_sentence_transformers: None):
    emb = LocalSentenceTransformerEmbedder(model_name="intfloat/multilingual-e5-small")
    assert emb.name == "local_st"
    assert emb.model == "intfloat/multilingual-e5-small"


def test_normalize_flag_propagates_to_encode(fake_sentence_transformers: None):
    emb = LocalSentenceTransformerEmbedder(
        model_name="intfloat/multilingual-e5-small", normalize=True
    )
    emb.embed(["x"])

    assert _FakeSentenceTransformer.last_instance is not None
    kwargs = _FakeSentenceTransformer.last_instance.encoded_kwargs[0]
    assert kwargs["normalize_embeddings"] is True


def test_missing_dependency_raises_import_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    emb = LocalSentenceTransformerEmbedder(model_name="intfloat/multilingual-e5-small")

    with pytest.raises(ImportError, match="sentence-transformers is not installed"):
        emb.embed(["x"])

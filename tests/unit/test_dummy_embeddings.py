# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

import math

import pytest

from open_data_jalisco.adapters.embeddings.dummy import DummyEmbeddingProvider


def test_dimension_matches():
    p = DummyEmbeddingProvider(dimension=64)
    [v] = p.embed(["any text"])
    assert len(v) == 64


def test_deterministic_for_same_input():
    p = DummyEmbeddingProvider(dimension=32)
    a = p.embed(["alpha", "beta"])
    b = p.embed(["alpha", "beta"])
    assert a == b


def test_different_inputs_produce_different_vectors():
    p = DummyEmbeddingProvider(dimension=32)
    [a, b] = p.embed(["alpha", "omega"])
    assert a != b


def test_vectors_are_unit_normalized():
    p = DummyEmbeddingProvider(dimension=128)
    [v] = p.embed(["normalize me"])
    norm = math.sqrt(sum(x * x for x in v))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_rejects_non_positive_dimension():
    with pytest.raises(ValueError):
        DummyEmbeddingProvider(dimension=0)

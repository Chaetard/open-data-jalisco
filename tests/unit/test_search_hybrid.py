# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Reciprocal Rank Fusion of the vector and lexical search arms."""
from open_data_jalisco.search_service import _fuse

from ._api_helpers import make_chunk, make_document


def _chunk(text: str):
    return make_chunk(make_document(), text=text)


def test_fuse_rewards_agreement_between_arms():
    # A chunk that both arms rank highly should beat one only a single arm liked.
    both = _chunk("a")
    vec_only = _chunk("b")
    lex_only = _chunk("c")

    vector = [(both, 0.1), (vec_only, 0.2)]
    lexical = [(both, 5.0), (lex_only, 4.0)]

    fused = _fuse(vector, lexical, limit=10)
    ids = [c.id for c, _ in fused]
    assert ids[0] == both.id  # appears in both lists -> highest RRF
    assert set(ids) == {both.id, vec_only.id, lex_only.id}  # union, deduped


def test_fuse_surfaces_lexical_only_hits():
    # The whole point of hybrid: a chunk the vector arm missed (exact code) still
    # enters the pool via the lexical arm, carrying no vector distance.
    lex_only = _chunk("partida 333")
    fused = _fuse([], [(lex_only, 2.0)], limit=10)
    assert fused == [(lex_only, None)]


def test_fuse_keeps_vector_distance_for_scoring():
    c = _chunk("x")
    fused = _fuse([(c, 0.42)], [], limit=10)
    assert fused[0][1] == 0.42

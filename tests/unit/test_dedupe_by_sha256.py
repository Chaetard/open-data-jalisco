# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Unit tests for the search-time sha256 dedup helper.

Why this exists: SAPUMU re-publishes the same PDF under multiple URLs, so a
``semantic_search`` would otherwise return the same content N times. The
helper collapses those at the search layer (no schema change, no ingest-time
policy change) so the user sees one hit per unique file.
"""
from __future__ import annotations

from open_data_jalisco.adapters.persistence.chunk_repository import dedupe_by_sha256
from open_data_jalisco.domain.chunk import Chunk
from open_data_jalisco.domain.enums import DocumentType
from open_data_jalisco.shared.time import utcnow


def _chunk(sha: str, *, text: str = "x") -> Chunk:
    return Chunk(
        document_id=__import__("uuid").uuid4(),
        source_id=__import__("uuid").uuid4(),
        sha256=sha,
        chunk_index=0,
        text=text,
        char_count=len(text),
        captured_at=utcnow(),
        municipality="Tala",
        document_type=DocumentType.OTHER,
        year=2025,
    )


def test_first_hit_per_sha256_is_kept_and_order_is_preserved():
    a1, a2, a3 = _chunk("aaa"), _chunk("aaa"), _chunk("aaa")
    b1 = _chunk("bbb")
    c1, c2 = _chunk("ccc"), _chunk("ccc")
    ranked = [(a1, 0.10), (a2, 0.11), (b1, 0.20), (a3, 0.25), (c1, 0.30), (c2, 0.31)]

    out = dedupe_by_sha256(ranked, limit=10)

    assert [d for _, d in out] == [0.10, 0.20, 0.30]
    assert [c.sha256 for c, _ in out] == ["aaa", "bbb", "ccc"]


def test_limit_stops_iteration_after_enough_unique_hits():
    a = _chunk("aaa")
    b = _chunk("bbb")
    c = _chunk("ccc")
    ranked = [(a, 0.1), (b, 0.2), (c, 0.3)]

    out = dedupe_by_sha256(ranked, limit=2)

    assert len(out) == 2
    assert [c.sha256 for c, _ in out] == ["aaa", "bbb"]


def test_all_duplicates_collapses_to_single_hit():
    """The original bug report: 5 SAPUMU URLs, 1 sha256, search returns 5 hits."""
    sha = "11542efbb1f82abda4c4c16c18f6eb37331e0e91f7a5f09ab39f5ca19b311dcf"
    ranked = [(_chunk(sha), 0.085 + i * 0.001) for i in range(5)]

    out = dedupe_by_sha256(ranked, limit=5)

    assert len(out) == 1
    assert out[0][0].sha256 == sha
    assert out[0][1] == 0.085


def test_empty_input_returns_empty_list():
    assert dedupe_by_sha256(iter(()), limit=5) == []


def test_consumes_generator_lazily_and_stops_at_limit():
    """Should not materialize the whole ranked stream when limit is satisfied early."""
    consumed: list[str] = []

    def stream():
        for sha in ("aaa", "bbb", "ccc", "ddd", "eee"):
            consumed.append(sha)
            yield _chunk(sha), 0.1

    out = dedupe_by_sha256(stream(), limit=2)

    assert len(out) == 2
    # The generator should not have been pulled beyond what was needed.
    assert consumed == ["aaa", "bbb"]

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Tests for the resumability + no-cap additions to discovered ingest.

Why: large bulk ingests (~2400+ PDFs) can take 1-2 hours and may be cut by
network blips. The pre-download URL skip + the no-cap limit option together
make re-runs cheap (only fetch what we don't already have).
"""
from __future__ import annotations

from typing import Any

from open_data_jalisco.discovery.candidates_ingest import (
    CandidateIngestFilter,
    filter_out_known_urls,
    select_entries,
)
from open_data_jalisco.ports.scraper import ScraperPlanEntry


def _cand(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "url": "https://app-sapumu.example.com/tala/a.pdf",
        "title": "a",
        "extension": "pdf",
        "year": 2025,
        "content_id": 63,
        "content_title": "Reglamentos",
    }
    base.update(overrides)
    return base


def _entry(url: str) -> ScraperPlanEntry:
    return ScraperPlanEntry(
        url=url, source="discovered", title=None, document_type=None,
        year=2025, metadata={},
    )


# ---------------------------------------------------------------------------
# filter_out_known_urls
# ---------------------------------------------------------------------------


def test_filter_out_known_urls_skips_known_and_keeps_unknown():
    entries = [_entry("https://a"), _entry("https://b"), _entry("https://c")]
    known = {"https://a", "https://c"}

    remaining, skipped = filter_out_known_urls(entries, known)

    assert [e.url for e in remaining] == ["https://b"]
    assert [s["url"] for s in skipped] == ["https://a", "https://c"]
    assert all(s["reason"] == "already_in_db" for s in skipped)


def test_filter_out_known_urls_empty_set_is_noop():
    entries = [_entry("https://a"), _entry("https://b")]
    remaining, skipped = filter_out_known_urls(entries, set())

    assert remaining == entries
    assert skipped == []


def test_filter_out_known_urls_all_known_returns_empty():
    entries = [_entry("https://a"), _entry("https://b")]
    remaining, skipped = filter_out_known_urls(entries, {"https://a", "https://b"})

    assert remaining == []
    assert len(skipped) == 2


# ---------------------------------------------------------------------------
# CandidateIngestFilter(limit=None) — uncapped ingest
# ---------------------------------------------------------------------------


def test_select_entries_with_no_limit_yields_all_matching_candidates():
    cands = [
        _cand(url=f"https://app-sapumu.example.com/{i}.pdf") for i in range(2500)
    ]
    entries, skipped = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(limit=None),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert len(entries) == 2500
    assert skipped == []


def test_select_entries_explicit_numeric_limit_still_works():
    """The numeric cap still caps when set — None is the only no-cap signal."""
    cands = [_cand(url=f"https://app-sapumu.example.com/{i}.pdf") for i in range(10)]
    entries, _ = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(limit=3),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert len(entries) == 3

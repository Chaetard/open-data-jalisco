# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Inspect a discovered-candidates JSON file produced by ``sapumu scan``.

Pure logic only: loading is a thin JSON read, everything else is offline
aggregation/filtering over plain dicts. The CLI wrapper in
``open_data_jalisco.cli`` is responsible for I/O and presentation.

This module exists so the user can audit what ``sapumu scan`` discovered
*before* committing to any ingestion: no documents are downloaded, no DB
writes happen, docs/MANIFEST.md is untouched.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class CandidatesInspectError(Exception):
    """Raised when the input file is missing or doesn't look like a scan export."""


@dataclass(frozen=True)
class CandidateFilter:
    """Optional filters applied before aggregation.

    ``None`` on any field disables that filter. ``limit`` only affects the
    ``first_documents`` showcase; aggregations always cover the full filtered
    set.
    """

    year: int | None = None
    extension: str | None = None
    content_id: int | None = None
    limit: int = 10

    def matches(self, candidate: dict[str, Any]) -> bool:
        if self.year is not None and candidate.get("year") != self.year:
            return False
        if self.extension is not None:
            ext = candidate.get("extension")
            if ext is None or str(ext).lower().lstrip(".") != self.extension.lower().lstrip("."):
                return False
        if self.content_id is not None and candidate.get("content_id") != self.content_id:
            return False
        return True


@dataclass
class ContentBreakdown:
    content_id: int | None
    content_title: str | None
    count: int


@dataclass
class InspectionReport:
    """Aggregations over a filtered set of candidates."""

    total: int = 0
    by_extension: dict[str, int] = field(default_factory=dict)
    by_year: dict[str, int] = field(default_factory=dict)
    by_content: list[ContentBreakdown] = field(default_factory=list)
    top_content_titles: list[tuple[str, int]] = field(default_factory=list)
    first_documents: list[dict[str, Any]] = field(default_factory=list)
    duplicate_urls: list[tuple[str, int]] = field(default_factory=list)
    missing_title_count: int = 0
    missing_date_at_count: int = 0
    total_size_bytes: int = 0
    candidates_with_known_size: int = 0

    @property
    def total_size_mb(self) -> float:
        return round(self.total_size_bytes / (1024 * 1024), 2)


def load_candidates(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read a scan-export JSON file and return ``(candidates, metadata)``.

    ``metadata`` is the export payload minus the ``candidates`` list, so callers
    can show e.g. the template / pages_checked alongside the inspection.

    Raises ``CandidatesInspectError`` for missing files, unparseable JSON, or
    payloads that don't carry a ``candidates`` array.
    """
    if not path.exists():
        raise CandidatesInspectError(f"file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise CandidatesInspectError(f"invalid JSON in {path}: {e}") from e
    if not isinstance(data, dict):
        raise CandidatesInspectError(
            f"expected a JSON object at root of {path}, got {type(data).__name__}"
        )
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        raise CandidatesInspectError(
            f"{path}: missing 'candidates' array (is this a scan export?)"
        )
    metadata = {k: v for k, v in data.items() if k != "candidates"}
    return candidates, metadata


def apply_filters(
    candidates: Iterable[dict[str, Any]],
    filter_spec: CandidateFilter,
) -> list[dict[str, Any]]:
    return [c for c in candidates if isinstance(c, dict) and filter_spec.matches(c)]


def build_report(
    candidates: list[dict[str, Any]],
    *,
    limit_first: int = 10,
    top_titles: int = 20,
) -> InspectionReport:
    """Compute the inspection report over an already-filtered candidate list."""
    report = InspectionReport(total=len(candidates))
    if not candidates:
        return report

    ext_counter: Counter[str] = Counter()
    year_counter: Counter[str] = Counter()
    content_counter: Counter[tuple[int | None, str | None]] = Counter()
    title_counter: Counter[str] = Counter()
    url_counter: Counter[str] = Counter()

    for c in candidates:
        ext = c.get("extension")
        ext_key = str(ext).lower().lstrip(".") if ext else "(unknown)"
        ext_counter[ext_key] += 1

        year = c.get("year")
        year_key = str(year) if year is not None else "(unknown)"
        year_counter[year_key] += 1

        content_counter[(c.get("content_id"), c.get("content_title"))] += 1

        title = c.get("content_title")
        if title:
            title_counter[str(title)] += 1

        url = c.get("url")
        if url:
            url_counter[str(url)] += 1

        if not c.get("title"):
            report.missing_title_count += 1
        if not c.get("date_at"):
            report.missing_date_at_count += 1

        size = c.get("size")
        if isinstance(size, int) and size > 0:
            report.total_size_bytes += size
            report.candidates_with_known_size += 1

    report.by_extension = dict(ext_counter.most_common())
    report.by_year = dict(sorted(year_counter.items(), key=_year_sort_key))

    grouped: dict[tuple[int | None, str | None], int] = defaultdict(int)
    for key, count in content_counter.items():
        grouped[key] += count
    report.by_content = sorted(
        (
            ContentBreakdown(content_id=cid, content_title=ctitle, count=count)
            for (cid, ctitle), count in grouped.items()
        ),
        key=lambda cb: (-cb.count, cb.content_id or 0),
    )

    report.top_content_titles = title_counter.most_common(top_titles)
    report.first_documents = candidates[: max(0, limit_first)]
    report.duplicate_urls = [
        (url, count) for url, count in url_counter.most_common() if count > 1
    ]
    return report


def _year_sort_key(item: tuple[str, int]) -> tuple[int, int, str]:
    """Sort known years descending, push '(unknown)' (or unparseable) to the end."""
    year_str, _ = item
    if year_str == "(unknown)":
        return (1, 0, "")
    try:
        return (0, -int(year_str), "")
    except ValueError:
        return (1, 0, year_str)

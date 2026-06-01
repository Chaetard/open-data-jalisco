"""Tests for the offline `discovered inspect` aggregation/filter logic."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from open_data_jalisco.discovery.candidates_inspect import (
    CandidateFilter,
    CandidatesInspectError,
    apply_filters,
    build_report,
    load_candidates,
)


def _cand(**overrides: Any) -> dict[str, Any]:
    """Build a candidate dict with defaults; override any field per call."""
    base: dict[str, Any] = {
        "url": "https://f.example.com/a.pdf",
        "title": "Doc A",
        "slug": "doc-a",
        "date_at": "2025-11-15",
        "file_name": "a.pdf",
        "mime_type": "application/pdf",
        "size": 1024,
        "extension": "pdf",
        "year": 2025,
        "month": 11,
        "content_id": 63,
        "content_title": "Contenido 63",
        "source_page": "https://t.example.com/c/63",
    }
    base.update(overrides)
    return base


def _export(candidates: list[dict[str, Any]], **metadata: Any) -> dict[str, Any]:
    """Build a scan-export payload around a candidates list."""
    payload = {
        "template": "https://t.example.com/c/{id}",
        "section": "articulo_8",
        "from_id": 1,
        "to_id": 100,
        "pages_checked": 100,
        "pages_found": 95,
        "pages_with_documents": 44,
        "documents_found": len(candidates),
        "candidates": candidates,
    }
    payload.update(metadata)
    return payload


# ----------------------------- load_candidates ----------------------------


def test_load_candidates_returns_list_and_metadata(tmp_path: Path):
    src = tmp_path / "candidates.json"
    src.write_text(json.dumps(_export([_cand()])), encoding="utf-8")
    candidates, meta = load_candidates(src)
    assert len(candidates) == 1
    assert candidates[0]["url"].endswith("a.pdf")
    assert meta["template"] == "https://t.example.com/c/{id}"
    assert "candidates" not in meta


def test_load_candidates_missing_file(tmp_path: Path):
    with pytest.raises(CandidatesInspectError, match="not found"):
        load_candidates(tmp_path / "nope.json")


def test_load_candidates_invalid_json(tmp_path: Path):
    src = tmp_path / "broken.json"
    src.write_text("{not json", encoding="utf-8")
    with pytest.raises(CandidatesInspectError, match="invalid JSON"):
        load_candidates(src)


def test_load_candidates_rejects_array_at_root(tmp_path: Path):
    src = tmp_path / "arr.json"
    src.write_text(json.dumps([{"x": 1}]), encoding="utf-8")
    with pytest.raises(CandidatesInspectError, match="JSON object"):
        load_candidates(src)


def test_load_candidates_rejects_missing_candidates_array(tmp_path: Path):
    src = tmp_path / "wrong_shape.json"
    src.write_text(json.dumps({"template": "x"}), encoding="utf-8")
    with pytest.raises(CandidatesInspectError, match="candidates"):
        load_candidates(src)


# ----------------------------- filters ------------------------------------


def test_filter_year_exact_match():
    cands = [
        _cand(year=2025),
        _cand(year=2026),
        _cand(year=None),
    ]
    filtered = apply_filters(cands, CandidateFilter(year=2025))
    assert len(filtered) == 1
    assert filtered[0]["year"] == 2025


def test_filter_extension_is_case_insensitive_and_dot_tolerant():
    cands = [
        _cand(extension="PDF"),
        _cand(extension="pdf"),
        _cand(extension="xlsx"),
        _cand(extension=None),
    ]
    filtered_lower = apply_filters(cands, CandidateFilter(extension="pdf"))
    assert len(filtered_lower) == 2
    filtered_dotted = apply_filters(cands, CandidateFilter(extension=".PDF"))
    assert len(filtered_dotted) == 2


def test_filter_content_id_exact_match():
    cands = [_cand(content_id=63), _cand(content_id=64), _cand(content_id=63)]
    filtered = apply_filters(cands, CandidateFilter(content_id=63))
    assert len(filtered) == 2


def test_filter_combines_year_extension_content_id():
    cands = [
        _cand(year=2025, extension="pdf", content_id=63),
        _cand(year=2025, extension="xlsx", content_id=63),
        _cand(year=2026, extension="pdf", content_id=63),
        _cand(year=2025, extension="pdf", content_id=64),
    ]
    filtered = apply_filters(
        cands, CandidateFilter(year=2025, extension="pdf", content_id=63)
    )
    assert len(filtered) == 1


def test_filter_skips_non_dict_entries():
    """Malformed entries (e.g. nulls) must not crash filtering."""
    cands = [_cand(), None, "garbage", {"not": "a candidate"}]
    filtered = apply_filters(cands, CandidateFilter())  # type: ignore[arg-type]
    # The 'not a candidate' dict is still a dict and passes filter; "garbage" /
    # None are dropped. The matches() function tolerates missing keys.
    assert len(filtered) == 2


# ----------------------------- aggregation --------------------------------


def test_build_report_empty_returns_zeros():
    report = build_report([])
    assert report.total == 0
    assert report.by_extension == {}
    assert report.first_documents == []
    assert report.total_size_mb == 0.0


def test_build_report_counts_by_extension_and_year():
    cands = [
        _cand(extension="pdf", year=2025),
        _cand(extension="pdf", year=2025),
        _cand(extension="xlsx", year=2026),
        _cand(extension=None, year=None),
    ]
    report = build_report(cands)
    assert report.by_extension == {"pdf": 2, "xlsx": 1, "(unknown)": 1}
    # Years sorted descending with '(unknown)' last.
    assert list(report.by_year.items()) == [
        ("2026", 1),
        ("2025", 2),
        ("(unknown)", 1),
    ]


def test_build_report_groups_by_content_id_title():
    cands = [
        _cand(content_id=63, content_title="A"),
        _cand(content_id=63, content_title="A"),
        _cand(content_id=64, content_title="B"),
    ]
    report = build_report(cands)
    by_content = {(b.content_id, b.content_title): b.count for b in report.by_content}
    assert by_content == {(63, "A"): 2, (64, "B"): 1}
    # Sorted by count desc.
    assert report.by_content[0].count == 2


def test_build_report_top_content_titles_caps_to_20():
    cands = []
    for i in range(30):
        cands.append(_cand(content_id=i, content_title=f"Content {i}"))
    cands.extend(
        _cand(content_id=0, content_title="Content 0") for _ in range(10)
    )
    report = build_report(cands, top_titles=20)
    assert len(report.top_content_titles) == 20
    # 'Content 0' has 11 occurrences, must be top.
    assert report.top_content_titles[0] == ("Content 0", 11)


def test_build_report_first_documents_respects_limit():
    cands = [_cand(url=f"https://f.example.com/{i}.pdf") for i in range(50)]
    report = build_report(cands, limit_first=5)
    assert len(report.first_documents) == 5
    assert [d["url"] for d in report.first_documents] == [
        f"https://f.example.com/{i}.pdf" for i in range(5)
    ]


def test_build_report_first_documents_limit_zero_allowed():
    cands = [_cand()]
    report = build_report(cands, limit_first=0)
    assert report.first_documents == []


def test_build_report_detects_duplicate_urls():
    shared = "https://f.example.com/shared.pdf"
    cands = [
        _cand(url=shared),
        _cand(url=shared),
        _cand(url="https://f.example.com/unique.pdf"),
        _cand(url=shared),
    ]
    report = build_report(cands)
    assert report.duplicate_urls == [(shared, 3)]


def test_build_report_counts_missing_title_and_date_at():
    cands = [
        _cand(title=None, date_at=None),
        _cand(title="", date_at="2025-11-15"),
        _cand(title="Doc", date_at=None),
        _cand(title="Doc", date_at="2025-11-15"),
    ]
    report = build_report(cands)
    # title=None and title="" both count as missing.
    assert report.missing_title_count == 2
    assert report.missing_date_at_count == 2


def test_build_report_totals_size_in_mb():
    """1 MiB = 1024*1024 bytes; sum should round to 2 decimals."""
    cands = [
        _cand(size=1024 * 1024),          # 1 MiB
        _cand(size=1024 * 1024 // 2),     # 0.5 MiB
        _cand(size=None),                 # unknown — skipped
        _cand(size=0),                    # zero — skipped
    ]
    report = build_report(cands)
    assert report.total_size_bytes == int(1024 * 1024 * 1.5)
    assert report.total_size_mb == 1.5
    assert report.candidates_with_known_size == 2


def test_build_report_ignores_non_int_size():
    cands = [_cand(size="123KB"), _cand(size=1024)]
    report = build_report(cands)
    assert report.total_size_bytes == 1024
    assert report.candidates_with_known_size == 1


# ----------------------------- CLI smoke ----------------------------------


def test_cli_inspect_runs_against_real_export(tmp_path: Path):
    """End-to-end: write a real export file, invoke CLI, check exit code."""
    from typer.testing import CliRunner

    from open_data_jalisco import cli as cli_module

    cands = [
        _cand(url="https://f.example.com/a.pdf", year=2025, extension="pdf"),
        _cand(url="https://f.example.com/b.xlsx", year=2025, extension="xlsx"),
        _cand(url="https://f.example.com/c.pdf", year=2026, extension="pdf"),
    ]
    src = tmp_path / "candidates.json"
    src.write_text(json.dumps(_export(cands)), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        ["discovered", "inspect", str(src), "--year", "2025"],
    )
    assert result.exit_code == 0, result.output
    # The header reports the filter ran.
    assert "year=2025" in result.output
    # After filter we should have 2 candidates.
    assert "after filters:  2" in result.output


def test_cli_inspect_reports_error_for_missing_file(tmp_path: Path):
    """Typer's `exists=True` already rejects missing paths with exit code 2."""
    from typer.testing import CliRunner

    from open_data_jalisco import cli as cli_module

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        ["discovered", "inspect", str(tmp_path / "nope.json")],
    )
    assert result.exit_code != 0


def test_cli_inspect_handles_empty_filtered_set(tmp_path: Path):
    from typer.testing import CliRunner

    from open_data_jalisco import cli as cli_module

    src = tmp_path / "candidates.json"
    src.write_text(json.dumps(_export([_cand(year=2025)])), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        ["discovered", "inspect", str(src), "--year", "1999"],
    )
    assert result.exit_code == 0, result.output
    assert "no candidates after filters" in result.output

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Tests for the SAPUMU discovery (``sapumu scan-content``) logic."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_data_jalisco.discovery.sapumu_scan import (
    SapumuScanConfig,
    SapumuScanError,
    export_candidates,
    scan_content_pages,
)


def _payload(content_id: int, files: list[dict]) -> dict:
    return {
        "id": content_id,
        "title": f"Content {content_id}",
        "grouped_media": [
            {
                "year": 2025,
                "months": [
                    {"month": 11, "files": files},
                ],
            }
        ],
    }


def _wrap(payload: dict) -> str:
    encoded = json.dumps(payload).replace('"', "&quot;")
    return f'<html><body><level-content :content="{encoded}"></level-content></body></html>'


def test_config_validation_requires_id_placeholder():
    cfg = SapumuScanConfig(template="https://t.example.com/c/63", from_id=1, to_id=2)
    with pytest.raises(SapumuScanError, match=r"\{id\}"):
        cfg.validate()


def test_config_validation_rejects_reverse_range():
    cfg = SapumuScanConfig(template="https://t.example.com/c/{id}", from_id=10, to_id=1)
    with pytest.raises(SapumuScanError, match="to_id"):
        cfg.validate()


def test_config_validation_rejects_zero_ids():
    cfg = SapumuScanConfig(template="https://t.example.com/c/{id}", from_id=0, to_id=5)
    with pytest.raises(SapumuScanError):
        cfg.validate()


def test_urls_builds_full_range():
    cfg = SapumuScanConfig(template="https://t.example.com/c/{id}", from_id=1, to_id=3)
    assert cfg.urls() == [
        "https://t.example.com/c/1",
        "https://t.example.com/c/2",
        "https://t.example.com/c/3",
    ]


def test_scan_finds_documents_across_pages():
    pages: dict[str, str] = {
        "https://t.example.com/c/1": _wrap(
            _payload(1, [{"full_url": "https://f.example.com/1/a.pdf", "extension": "pdf"}])
        ),
        "https://t.example.com/c/2": _wrap(
            _payload(2, [{"full_url": "https://f.example.com/2/b.pdf", "extension": "pdf"}])
        ),
        "https://t.example.com/c/3": "<html>no level-content</html>",
    }

    def fetcher(url: str) -> str:
        return pages[url]

    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=3,
        delay_seconds=0.0,
        allowed_domains=["f.example.com"],
        document_extensions=["pdf"],
    )
    sleeps: list[float] = []
    result = scan_content_pages(cfg, html_fetcher=fetcher, sleep=sleeps.append)

    assert result.pages_checked == 3
    assert result.pages_with_documents == 2
    assert result.pages_no_documents == 1
    assert result.pages_failed == 0
    assert result.documents_found == 2
    assert sorted(c.url for c in result.candidates) == [
        "https://f.example.com/1/a.pdf",
        "https://f.example.com/2/b.pdf",
    ]
    # No delay configured.
    assert sleeps == []


def test_scan_respects_delay_between_requests():
    def fetcher(_url: str) -> str:
        return _wrap(_payload(0, []))

    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=4,
        delay_seconds=0.5,
    )
    sleeps: list[float] = []
    scan_content_pages(cfg, html_fetcher=fetcher, sleep=sleeps.append)
    # 4 pages → 3 inter-request sleeps of 0.5s each.
    assert sleeps == [0.5, 0.5, 0.5]


def test_scan_records_fetch_errors_without_aborting():
    def fetcher(url: str) -> str:
        if "/2" in url:
            raise RuntimeError("HTTP 500 on page 2")
        return _wrap(
            _payload(0, [{"full_url": "https://f.example.com/x.pdf", "extension": "pdf"}])
        )

    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=3,
        delay_seconds=0.0,
        allowed_domains=["f.example.com"],
        document_extensions=["pdf"],
    )
    result = scan_content_pages(cfg, html_fetcher=fetcher, sleep=lambda _: None)

    assert result.pages_checked == 3
    assert result.pages_failed == 1
    # Pages 1 and 3 succeeded — but they yield the same URL, so the second is deduped.
    assert result.documents_found == 1
    assert len(result.errors) == 1
    assert "HTTP 500" in result.errors[0]["error"]


def test_scan_dedupes_documents_across_pages():
    shared = "https://f.example.com/shared.pdf"
    pages = {
        "https://t.example.com/c/1": _wrap(
            _payload(1, [{"full_url": shared, "extension": "pdf"}])
        ),
        "https://t.example.com/c/2": _wrap(
            _payload(2, [{"full_url": shared, "extension": "pdf"}])
        ),
    }
    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=2,
        delay_seconds=0.0,
        allowed_domains=["f.example.com"],
        document_extensions=["pdf"],
    )
    result = scan_content_pages(
        cfg, html_fetcher=lambda url: pages[url], sleep=lambda _: None
    )
    assert result.documents_found == 1
    assert any(s["reason"] == "duplicate" for s in result.skipped)


def test_scan_filters_by_allowed_domains():
    pages = {
        "https://t.example.com/c/1": _wrap(
            _payload(
                1,
                [
                    {"full_url": "https://f.example.com/ok.pdf", "extension": "pdf"},
                    {"full_url": "https://evil.example.com/bad.pdf", "extension": "pdf"},
                ],
            )
        ),
    }
    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=1,
        delay_seconds=0.0,
        allowed_domains=["f.example.com"],
        document_extensions=["pdf"],
    )
    result = scan_content_pages(
        cfg, html_fetcher=lambda url: pages[url], sleep=lambda _: None
    )
    assert result.documents_found == 1
    assert any(s["reason"].startswith("domain_not_allowed") for s in result.skipped)


def test_export_json(tmp_path: Path):
    pages = {
        "https://t.example.com/c/1": _wrap(
            _payload(1, [{"full_url": "https://f.example.com/x.pdf", "extension": "pdf"}])
        ),
    }
    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=1,
        delay_seconds=0.0,
        allowed_domains=["f.example.com"],
        document_extensions=["pdf"],
    )
    result = scan_content_pages(
        cfg, html_fetcher=lambda url: pages[url], sleep=lambda _: None
    )
    out = tmp_path / "candidates.json"
    export_candidates(result, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["documents_found"] == 1
    assert data["candidates"][0]["url"] == "https://f.example.com/x.pdf"


def test_export_yaml(tmp_path: Path):
    import yaml as yaml_mod

    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=1,
        delay_seconds=0.0,
    )
    result = scan_content_pages(
        cfg, html_fetcher=lambda _u: "", sleep=lambda _: None
    )
    out = tmp_path / "candidates.yaml"
    export_candidates(result, out)
    data = yaml_mod.safe_load(out.read_text(encoding="utf-8"))
    assert data["template"] == cfg.template
    assert data["candidates"] == []


def test_export_rejects_unknown_format(tmp_path: Path):
    cfg = SapumuScanConfig(template="https://t.example.com/c/{id}", from_id=1, to_id=1)
    result = scan_content_pages(
        cfg, html_fetcher=lambda _u: "", sleep=lambda _: None
    )
    with pytest.raises(SapumuScanError, match="unsupported"):
        export_candidates(result, tmp_path / "candidates.txt")


def test_scan_returns_empty_for_pages_without_documents():
    """Pages that exist but lack <level-content> count as no_documents, not failed."""
    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=2,
        delay_seconds=0.0,
    )
    result = scan_content_pages(
        cfg,
        html_fetcher=lambda _u: "<html>nothing</html>",
        sleep=lambda _: None,
    )
    assert result.pages_no_documents == 2
    assert result.pages_failed == 0
    assert result.pages_found == 0
    assert result.documents_found == 0


def test_limit_pages_caps_iteration_within_range():
    """`limit_pages` stops the scan early even when --to-id allows more."""
    visited: list[str] = []

    def fetcher(url: str) -> str:
        visited.append(url)
        return ""

    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=100,
        delay_seconds=0.0,
        limit_pages=3,
    )
    cfg.validate()
    assert cfg.effective_page_count == 3
    assert cfg.urls() == [
        "https://t.example.com/c/1",
        "https://t.example.com/c/2",
        "https://t.example.com/c/3",
    ]
    result = scan_content_pages(cfg, html_fetcher=fetcher, sleep=lambda _: None)
    assert visited == cfg.urls()
    assert result.pages_checked == 3
    assert result.limit_pages == 3


def test_limit_pages_rejects_zero():
    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=10,
        limit_pages=0,
    )
    with pytest.raises(SapumuScanError, match="limit_pages"):
        cfg.validate()


def test_pages_found_counts_valid_level_content_with_or_without_files():
    """A page with level-content but zero files is still ``pages_found``."""
    pages = {
        "https://t.example.com/c/1": _wrap(_payload(1, [])),  # level-content, no files
        "https://t.example.com/c/2": _wrap(
            _payload(2, [{"full_url": "https://f.example.com/x.pdf", "extension": "pdf"}])
        ),
        "https://t.example.com/c/3": "<html>no level-content</html>",
    }
    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=3,
        delay_seconds=0.0,
        allowed_domains=["f.example.com"],
        document_extensions=["pdf"],
    )
    result = scan_content_pages(
        cfg, html_fetcher=lambda url: pages[url], sleep=lambda _: None
    )
    assert result.pages_found == 2
    assert result.pages_with_documents == 1
    # Page 1 (level-content, 0 files) and page 3 (no level-content) both
    # contribute to pages_no_documents.
    assert result.pages_no_documents == 2


def test_sample_documents_returns_first_n_as_dicts():
    files = [
        {"full_url": f"https://f.example.com/d{i}.pdf", "extension": "pdf", "id": i}
        for i in range(10)
    ]
    pages = {"https://t.example.com/c/1": _wrap(_payload(1, files))}
    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=1,
        delay_seconds=0.0,
        allowed_domains=["f.example.com"],
        document_extensions=["pdf"],
    )
    result = scan_content_pages(
        cfg, html_fetcher=lambda url: pages[url], sleep=lambda _: None
    )
    sample = result.sample_documents(5)
    assert len(sample) == 5
    assert all(isinstance(s, dict) for s in sample)
    assert sample[0]["url"] == "https://f.example.com/d0.pdf"


def test_section_propagates_into_result_and_export(tmp_path: Path):
    cfg = SapumuScanConfig(
        template="https://t.example.com/c/{id}",
        from_id=1,
        to_id=1,
        delay_seconds=0.0,
        section="articulo_8",
    )
    result = scan_content_pages(
        cfg, html_fetcher=lambda _u: "", sleep=lambda _: None
    )
    assert result.section == "articulo_8"

    out = tmp_path / "candidates.json"
    export_candidates(result, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["section"] == "articulo_8"
    assert "pages_found" in data
    assert "limit_pages" in data


def test_resolve_section_template_prefers_section_map():
    from open_data_jalisco.cli import _resolve_section_template

    scraper = {
        "content_page_template": "https://fallback.example.com/c/{id}",
        "section_templates": {
            "articulo_8": "https://x.example.com/articulo-8/c/{id}",
        },
    }
    assert (
        _resolve_section_template(scraper, "articulo_8")
        == "https://x.example.com/articulo-8/c/{id}"
    )


def test_resolve_section_template_falls_back_to_content_page_template():
    from open_data_jalisco.cli import _resolve_section_template

    scraper = {
        "content_page_template": "https://fallback.example.com/c/{id}",
        "section_templates": {"otro": "https://x.example.com/otro/c/{id}"},
    }
    # Unknown section → fallback.
    assert (
        _resolve_section_template(scraper, "articulo_8")
        == "https://fallback.example.com/c/{id}"
    )


def test_resolve_section_template_returns_none_when_nothing_configured():
    from open_data_jalisco.cli import _resolve_section_template

    assert _resolve_section_template({}, "articulo_8") is None
    assert _resolve_section_template({"section_templates": {}}, "articulo_8") is None


def _write_fake_source(tmp_path: Path) -> Path:
    """Write a minimal SAPUMU-shaped source YAML at ``tmp_path/datasets/sources/fake.yaml``.

    Returns the tmp_path root so tests can ``monkeypatch.chdir`` into it and let
    the default ``datasets/sources`` resolution find the fake source.
    """
    sources_dir = tmp_path / "datasets" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    (sources_dir / "fake.yaml").write_text(
        """
slug: fake
name: Fake
kind: municipal_portal
municipality: Fake
official_url: "https://t.example.com/"
is_active: true
scraper:
  type: sapumu_content
  allowed_domains: ["f.example.com"]
  document_extensions: ["pdf"]
  content_page_template: "https://t.example.com/fallback/{id}"
  section_templates:
    articulo_8: "https://t.example.com/articulo-8/{id}"
""",
        encoding="utf-8",
    )
    return tmp_path


def test_cli_scan_dry_run_uses_section_template(monkeypatch, tmp_path: Path):
    """`sapumu scan ... --dry-run` resolves the section template and lists URLs.

    Network is *not* touched; we patch find_source_config to point at the fake
    YAML and verify the JSON the CLI prints.
    """
    import json as _json

    from typer.testing import CliRunner

    from open_data_jalisco import cli as cli_module

    root = _write_fake_source(tmp_path)
    monkeypatch.chdir(root)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        [
            "sapumu",
            "scan",
            "fake",
            "--section",
            "articulo_8",
            "--from-id",
            "1",
            "--to-id",
            "3",
            "--limit-pages",
            "2",
            "--delay-ms",
            "0",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = _json.loads(result.output)
    assert payload["command"] == "sapumu scan"
    assert payload["source_slug"] == "fake"
    assert payload["section"] == "articulo_8"
    assert payload["template"] == "https://t.example.com/articulo-8/{id}"
    # --limit-pages caps the 3-id range to 2 URLs.
    assert payload["effective_page_count"] == 2
    assert payload["urls_to_fetch"] == [
        "https://t.example.com/articulo-8/1",
        "https://t.example.com/articulo-8/2",
    ]
    assert payload["dry_run"] is True


def test_cli_scan_errors_when_range_inverted(monkeypatch, tmp_path: Path):
    from typer.testing import CliRunner

    from open_data_jalisco import cli as cli_module

    root = _write_fake_source(tmp_path)
    monkeypatch.chdir(root)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        [
            "sapumu",
            "scan",
            "fake",
            "--section",
            "articulo_8",
            "--from-id",
            "10",
            "--to-id",
            "1",
            "--dry-run",
        ],
    )
    assert result.exit_code == 2


def test_cli_scan_errors_when_section_unknown_and_no_fallback(
    monkeypatch, tmp_path: Path
):
    """Section unknown AND content_page_template missing → exit code 2."""
    import yaml as _yaml
    from typer.testing import CliRunner

    from open_data_jalisco import cli as cli_module

    sources_dir = tmp_path / "datasets" / "sources"
    sources_dir.mkdir(parents=True, exist_ok=True)
    (sources_dir / "fake.yaml").write_text(
        _yaml.safe_dump(
            {
                "slug": "fake",
                "name": "Fake",
                "kind": "municipal_portal",
                "municipality": "Fake",
                "official_url": "https://t.example.com/",
                "is_active": True,
                "scraper": {"type": "sapumu_content"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        [
            "sapumu",
            "scan",
            "fake",
            "--section",
            "articulo_8",
            "--from-id",
            "1",
            "--to-id",
            "1",
            "--dry-run",
        ],
    )
    assert result.exit_code == 2
    assert "no template" in result.output.lower()

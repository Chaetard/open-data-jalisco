"""Tests for the `discovered ingest` flow: filtering, validation, plan-entry
shape, and the use case's `execute_from_entries` path.

All collaborators are in-memory fakes. No network, no DB, no disk writes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import yaml

from open_data_jalisco.discovery.candidates_ingest import (
    SENSITIVE_CONTENT_IDS,
    CandidateIngestError,
    CandidateIngestFilter,
    select_entries,
)
from open_data_jalisco.domain.document import Document
from open_data_jalisco.domain.source import Source
from open_data_jalisco.ingestion import IngestSourceUseCase
from open_data_jalisco.ingestion import ingest_source as ingest_source_mod
from open_data_jalisco.ingestion import source_loader as source_loader_mod
from open_data_jalisco.ports.scraper import ScraperPlanEntry


def _cand(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "url": "https://app-sapumu.example.com/tala/content/2025/11/2743/a.pdf",
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
        "content_title": "Contenido 63 — Reglamentos",
        "source_page": "https://tala.example.com/c/63",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# select_entries: filters
# ---------------------------------------------------------------------------


def test_select_entries_filters_by_content_id_year_extension():
    cands = [
        _cand(content_id=63, year=2025, extension="pdf"),
        _cand(content_id=63, year=2025, extension="xlsx", url="https://app-sapumu.example.com/x.xlsx"),
        _cand(content_id=64, year=2025, extension="pdf", url="https://app-sapumu.example.com/y.pdf"),
        _cand(content_id=63, year=2024, extension="pdf", url="https://app-sapumu.example.com/z.pdf"),
    ]
    entries, skipped = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(
            content_id=63, year=2025, extension="pdf", limit=10
        ),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf", "xlsx"],
    )
    assert len(entries) == 1
    assert entries[0].url.endswith("/a.pdf")
    # The non-matching candidates were silently filtered out (not in skipped).
    assert skipped == []


def test_select_entries_content_title_substring_case_insensitive():
    cands = [
        _cand(content_title="Reglamentos", url="https://app-sapumu.example.com/1.pdf"),
        _cand(content_title="reglamentos municipales", url="https://app-sapumu.example.com/2.pdf"),
        _cand(content_title="Presupuesto", url="https://app-sapumu.example.com/3.pdf"),
    ]
    entries, _ = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(content_title="REGLAM", limit=10),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert {e.url for e in entries} == {
        "https://app-sapumu.example.com/1.pdf",
        "https://app-sapumu.example.com/2.pdf",
    }


def test_select_entries_respects_limit():
    cands = [
        _cand(url=f"https://app-sapumu.example.com/{i}.pdf") for i in range(50)
    ]
    entries, _ = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(limit=5),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert len(entries) == 5
    assert entries[0].url.endswith("/0.pdf")


def test_select_entries_rejects_negative_limit():
    with pytest.raises(CandidateIngestError, match="limit"):
        select_entries(
            [],
            filter_spec=CandidateIngestFilter(limit=-1),
            allowed_domains=None,
            document_extensions=None,
        )


# ---------------------------------------------------------------------------
# select_entries: sensitive content blocking
# ---------------------------------------------------------------------------


def test_select_entries_blocks_sensitive_content_id_by_default():
    """content_id 92 = declaraciones patrimoniales — refused without opt-in."""
    assert 92 in SENSITIVE_CONTENT_IDS
    cands = [
        _cand(content_id=92, url="https://app-sapumu.example.com/sensitive.pdf"),
        _cand(content_id=63, url="https://app-sapumu.example.com/ok.pdf"),
    ]
    entries, skipped = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(limit=10),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert len(entries) == 1
    assert entries[0].url.endswith("/ok.pdf")
    assert any(
        s["reason"].startswith("sensitive_content_id_blocked") for s in skipped
    )


def test_select_entries_allow_sensitive_overrides_block():
    cands = [
        _cand(content_id=92, url="https://app-sapumu.example.com/sensitive.pdf"),
    ]
    entries, skipped = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(limit=10, allow_sensitive_content=True),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert len(entries) == 1
    assert skipped == []


def test_select_entries_sensitive_block_uses_url_in_skipped_record():
    """We want the URL preserved in the skip reason so the CLI can show it."""
    cands = [_cand(content_id=92, url="https://app-sapumu.example.com/x.pdf")]
    _, skipped = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(limit=10),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert skipped == [
        {
            "url": "https://app-sapumu.example.com/x.pdf",
            "reason": "sensitive_content_id_blocked:92",
        }
    ]


# ---------------------------------------------------------------------------
# select_entries: validation, dedup, plan-entry shape
# ---------------------------------------------------------------------------


def test_select_entries_validates_against_allowed_domains():
    cands = [
        _cand(url="https://app-sapumu.example.com/ok.pdf"),
        _cand(url="https://evil.example.com/bad.pdf"),
    ]
    entries, skipped = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(limit=10),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert [e.url for e in entries] == ["https://app-sapumu.example.com/ok.pdf"]
    assert any(s["reason"].startswith("domain_not_allowed") for s in skipped)


def test_select_entries_validates_against_document_extensions():
    cands = [
        _cand(url="https://app-sapumu.example.com/ok.pdf"),
        _cand(url="https://app-sapumu.example.com/bad.exe"),
    ]
    _, skipped = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(limit=10),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert any(s["reason"] == "extension_not_allowed" for s in skipped)


def test_select_entries_dedupes_repeated_urls():
    shared = "https://app-sapumu.example.com/shared.pdf"
    cands = [_cand(url=shared), _cand(url=shared, content_id=64)]
    entries, skipped = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(limit=10),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert len(entries) == 1
    assert any(s["reason"] == "duplicate" for s in skipped)


def test_select_entries_skips_missing_url():
    cands = [_cand(url=""), _cand(url=None)]  # type: ignore[arg-type]
    entries, skipped = select_entries(
        cands,
        filter_spec=CandidateIngestFilter(limit=10),
        allowed_domains=None,
        document_extensions=None,
    )
    assert entries == []
    assert all(s["reason"] == "missing_url" for s in skipped)


def test_select_entries_ignores_non_dict_candidates():
    cands = [_cand(), None, "garbage", 42]
    entries, _ = select_entries(
        cands,  # type: ignore[arg-type]
        filter_spec=CandidateIngestFilter(limit=10),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert len(entries) == 1


def test_plan_entry_metadata_mirrors_sapumu_scraper_shape():
    """Ingested-from-candidates entries must look identical to live SAPUMU."""
    cand = _cand()
    entries, _ = select_entries(
        [cand],
        filter_spec=CandidateIngestFilter(limit=10),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    [entry] = entries
    assert isinstance(entry, ScraperPlanEntry)
    assert entry.source == "discovered"
    assert entry.title == "Doc A"
    assert entry.year == 2025
    assert entry.metadata["source_page"] == "https://tala.example.com/c/63"
    assert entry.metadata["ingested_from"] == "candidates_file"
    sapumu = entry.metadata["sapumu"]
    assert sapumu["content_id"] == 63
    assert sapumu["content_title"] == "Contenido 63 — Reglamentos"
    assert sapumu["date_at"] == "2025-11-15"
    assert sapumu["file_name"] == "a.pdf"
    assert sapumu["mime_type"] == "application/pdf"
    assert sapumu["size"] == 1024
    assert sapumu["extension"] == "pdf"
    assert sapumu["month"] == 11
    assert sapumu["year"] == 2025


def test_plan_entry_title_falls_back_to_file_name():
    cand = _cand(title=None, file_name="fallback.pdf")
    entries, _ = select_entries(
        [cand],
        filter_spec=CandidateIngestFilter(limit=10),
        allowed_domains=["app-sapumu.example.com"],
        document_extensions=["pdf"],
    )
    assert entries[0].title == "fallback.pdf"


# ---------------------------------------------------------------------------
# IngestSourceUseCase.execute_from_entries
# ---------------------------------------------------------------------------


class _InMemorySourceRepo:
    def __init__(self) -> None:
        self._by_slug: dict[str, Source] = {}

    def upsert(self, source: Source) -> Source:
        self._by_slug[source.slug] = source
        return source

    def get_by_slug(self, slug: str) -> Source | None:
        return self._by_slug.get(slug)


class _InMemoryDocRepo:
    def __init__(self) -> None:
        self.inserted: list[Document] = []

    def get_by_id(self, _id: UUID) -> Document | None:
        return None

    def find_by_url_and_hash(self, *_a, **_kw) -> Document | None:
        return None

    def find_current_by_url(self, _source_id: UUID, _url: str) -> Document | None:
        return None

    def insert_new_version(
        self, document: Document, supersedes: Document | None
    ) -> Document:
        self.inserted.append(document)
        return document

    def update(self, document: Document) -> Document:
        return document

    def list_documents(self, **_kw):
        return list(self.inserted)

    def list_pending(self, limit: int = 50, *, include_failed: bool = False):
        return []


class _RecordingRawStorage:
    def __init__(self) -> None:
        self.stored: list[bytes] = []

    def store(self, *, content, sha256, source_slug, captured_at, extension) -> str:
        self.stored.append(content)
        return f"{source_slug}/{sha256}.{extension}"

    def open(self, path):  # pragma: no cover
        raise NotImplementedError


def _write_source_yaml(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    cfg = {
        "slug": "tala",
        "name": "Tala test",
        "kind": "municipal_portal",
        "municipality": "Tala",
        "official_url": "https://tala.example.test/index",
        "is_active": True,
        "scraper": {
            "type": "sapumu_content",
            "allowed_domains": ["app-sapumu.example.com"],
            "document_extensions": ["pdf"],
        },
    }
    (directory / "tala.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")


@pytest.fixture
def sources_dir(tmp_path: Path, monkeypatch):
    _write_source_yaml(tmp_path)

    def _find(slug: str):
        return source_loader_mod.find_source_config(slug, directory=tmp_path)

    monkeypatch.setattr(ingest_source_mod, "find_source_config", _find)
    return tmp_path


def _entry(url: str = "https://app-sapumu.example.com/a.pdf", **md_overrides) -> ScraperPlanEntry:
    return ScraperPlanEntry(
        url=url,
        source="discovered",
        title="A",
        document_type=None,
        year=2025,
        metadata={
            "source_page": "https://tala.example.com/c/63",
            "sapumu": {"content_id": 63, "extension": "pdf", **md_overrides},
            "ingested_from": "candidates_file",
        },
    )


def test_execute_from_entries_dry_run_touches_no_repos(sources_dir: Path, monkeypatch):
    source_repo = _InMemorySourceRepo()
    doc_repo = _InMemoryDocRepo()
    raw = _RecordingRawStorage()
    use_case = IngestSourceUseCase(
        source_repo=source_repo, document_repo=doc_repo, raw_storage=raw
    )

    # build_scraper must NOT be called in dry-run — guard with a sentinel.
    def boom(*_a, **_kw):
        raise AssertionError("build_scraper called in dry-run")

    monkeypatch.setattr(ingest_source_mod, "build_scraper", boom)

    entries = [_entry(url=f"https://app-sapumu.example.com/{i}.pdf") for i in range(3)]
    result = use_case.execute_from_entries("tala", entries, dry_run=True)

    assert result.dry_run is True
    assert result.documents_seen == 3
    assert result.planned_urls == [e.url for e in entries]
    assert result.discovered_urls == [e.url for e in entries]
    assert source_repo._by_slug == {}
    assert doc_repo.inserted == []
    assert raw.stored == []


def test_execute_from_entries_persists_documents_with_sapumu_metadata(
    sources_dir: Path, monkeypatch
):
    class _FakeScraper:
        def fetch(self, _url: str) -> tuple[bytes, str, str]:
            return b"PDF-CONTENT", "application/pdf", "pdf"

    monkeypatch.setattr(
        ingest_source_mod, "build_scraper", lambda *_a, **_kw: _FakeScraper()
    )

    doc_repo = _InMemoryDocRepo()
    use_case = IngestSourceUseCase(
        source_repo=_InMemorySourceRepo(),
        document_repo=doc_repo,
        raw_storage=_RecordingRawStorage(),
    )

    entries = [_entry(url="https://app-sapumu.example.com/a.pdf")]
    result = use_case.execute_from_entries("tala", entries, dry_run=False)

    assert result.documents_seen == 1
    assert result.documents_inserted == 1
    [doc] = doc_repo.inserted
    assert doc.official_url == "https://app-sapumu.example.com/a.pdf"
    assert doc.title == "A"
    assert doc.year == 2025
    md = doc.metadata or {}
    assert md.get("source_page") == "https://tala.example.com/c/63"
    assert md.get("sapumu", {}).get("content_id") == 63
    assert md.get("ingested_from") == "candidates_file"


def test_execute_from_entries_skips_duplicates_against_existing_sha(
    sources_dir: Path, monkeypatch
):
    """A second run with the same content must be reported as unchanged."""

    class _FakeScraper:
        def fetch(self, _url: str) -> tuple[bytes, str, str]:
            return b"SAME-BYTES", "application/pdf", "pdf"

    monkeypatch.setattr(
        ingest_source_mod, "build_scraper", lambda *_a, **_kw: _FakeScraper()
    )

    class _DocRepoWithExisting(_InMemoryDocRepo):
        def find_current_by_url(self, _source_id, _url):
            if not self.inserted:
                return None
            return self.inserted[-1]

    doc_repo = _DocRepoWithExisting()
    use_case = IngestSourceUseCase(
        source_repo=_InMemorySourceRepo(),
        document_repo=doc_repo,
        raw_storage=_RecordingRawStorage(),
    )

    entries = [_entry()]
    first = use_case.execute_from_entries("tala", entries, dry_run=False)
    assert first.documents_inserted == 1

    second = use_case.execute_from_entries("tala", entries, dry_run=False)
    assert second.documents_inserted == 0
    assert second.documents_unchanged == 1


def test_execute_from_entries_reports_fetch_errors_without_aborting(
    sources_dir: Path, monkeypatch
):
    class _FlakyScraper:
        def __init__(self) -> None:
            self.calls = 0

        def fetch(self, url: str) -> tuple[bytes, str, str]:
            self.calls += 1
            if "/bad" in url:
                raise RuntimeError("HTTP 500")
            return b"OK", "application/pdf", "pdf"

    scraper = _FlakyScraper()
    monkeypatch.setattr(
        ingest_source_mod, "build_scraper", lambda *_a, **_kw: scraper
    )

    doc_repo = _InMemoryDocRepo()
    use_case = IngestSourceUseCase(
        source_repo=_InMemorySourceRepo(),
        document_repo=doc_repo,
        raw_storage=_RecordingRawStorage(),
    )

    entries = [
        _entry(url="https://app-sapumu.example.com/a.pdf"),
        _entry(url="https://app-sapumu.example.com/bad.pdf"),
        _entry(url="https://app-sapumu.example.com/b.pdf"),
    ]
    result = use_case.execute_from_entries("tala", entries, dry_run=False)

    assert result.documents_seen == 3
    assert result.documents_inserted == 2
    assert result.documents_failed == 1
    assert any("HTTP 500" in err for err in result.errors)
    assert scraper.calls == 3


# ---------------------------------------------------------------------------
# CLI smoke test (no network, no DB)
# ---------------------------------------------------------------------------


def _export(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "template": "https://tala.example.com/c/{id}",
        "section": "articulo_8",
        "from_id": 1,
        "to_id": 100,
        "candidates": candidates,
    }


def test_cli_discovered_ingest_dry_run_against_real_export(tmp_path: Path, monkeypatch):
    """End-to-end smoke through Typer's runner. No network, no DB."""
    from typer.testing import CliRunner

    from open_data_jalisco import cli as cli_module

    _write_source_yaml(tmp_path / "datasets" / "sources")

    cands_file = tmp_path / "candidates.json"
    cands = [
        _cand(content_id=63, url="https://app-sapumu.example.com/a.pdf"),
        _cand(content_id=63, url="https://app-sapumu.example.com/b.pdf"),
        _cand(content_id=92, url="https://app-sapumu.example.com/sensitive.pdf"),
        _cand(content_id=64, url="https://app-sapumu.example.com/other.pdf"),
    ]
    cands_file.write_text(json.dumps(_export(cands)), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        [
            "discovered",
            "ingest",
            str(cands_file),
            "--source",
            "tala",
            "--content-id",
            "63",
            "--year",
            "2025",
            "--extension",
            "pdf",
            "--limit",
            "10",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    # rich.print_json emits one JSON object spanning the whole output here
    # (no other prints precede it because nothing was blocked).
    payload = json.loads(result.output)
    assert payload["command"] == "discovered ingest"
    assert payload["source_slug"] == "tala"
    assert payload["dry_run"] is True
    assert sorted(payload["planned_urls"]) == [
        "https://app-sapumu.example.com/a.pdf",
        "https://app-sapumu.example.com/b.pdf",
    ]


def test_cli_discovered_ingest_blocks_sensitive_content_by_default(
    tmp_path: Path, monkeypatch
):
    from typer.testing import CliRunner

    from open_data_jalisco import cli as cli_module

    _write_source_yaml(tmp_path / "datasets" / "sources")

    cands = [
        _cand(content_id=92, url="https://app-sapumu.example.com/sensitive.pdf"),
    ]
    cands_file = tmp_path / "candidates.json"
    cands_file.write_text(json.dumps(_export(cands)), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        [
            "discovered",
            "ingest",
            str(cands_file),
            "--source",
            "tala",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "blocked 1 candidates" in result.output
    # No URLs planned at all.
    assert "no candidates passed the filters" in result.output


def test_cli_discovered_ingest_allow_sensitive_flag_unlocks_content_id_92(
    tmp_path: Path, monkeypatch
):
    from typer.testing import CliRunner

    from open_data_jalisco import cli as cli_module

    _write_source_yaml(tmp_path / "datasets" / "sources")

    cands = [
        _cand(content_id=92, url="https://app-sapumu.example.com/sensitive.pdf"),
    ]
    cands_file = tmp_path / "candidates.json"
    cands_file.write_text(json.dumps(_export(cands)), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        cli_module.app,
        [
            "discovered",
            "ingest",
            str(cands_file),
            "--source",
            "tala",
            "--allow-sensitive-content",
            "--dry-run",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "https://app-sapumu.example.com/sensitive.pdf" in result.output

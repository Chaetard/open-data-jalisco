"""Unit tests for the ingest use case: dry-run, limit, validation, placeholder rejection.

No network, no DB: all collaborators are in-memory fakes.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml

from open_data_jalisco.domain.document import Document
from open_data_jalisco.domain.enums import SourceKind
from open_data_jalisco.domain.source import Source
from open_data_jalisco.ingestion import (
    IngestSourceUseCase,
    PlaceholderUrlError,
)
from open_data_jalisco.ingestion import ingest_source as ingest_source_mod
from open_data_jalisco.ingestion import source_loader as source_loader_mod


class _InMemorySourceRepo:
    def __init__(self):
        self._by_slug: dict[str, Source] = {}

    def upsert(self, source: Source) -> Source:
        self._by_slug[source.slug] = source
        return source

    def get_by_slug(self, slug):
        return self._by_slug.get(slug)


class _InMemoryDocRepo:
    def __init__(self):
        self.inserted: list[Document] = []

    def get_by_id(self, _id):
        return None

    def find_by_url_and_hash(self, *a, **kw):
        return None

    def find_current_by_url(self, source_id: UUID, official_url: str):
        return None

    def insert_new_version(self, document: Document, supersedes):
        self.inserted.append(document)
        return document

    def update(self, document: Document) -> Document:
        return document

    def list_documents(self, **kw):
        return list(self.inserted)

    def list_pending(self, limit: int = 50, *, include_failed: bool = False):
        return []


class _RecordingRawStorage:
    def __init__(self):
        self.stored: list[bytes] = []

    def store(self, *, content, sha256, source_slug, captured_at, extension) -> str:
        self.stored.append(content)
        return f"{source_slug}/{sha256}.{extension}"

    def open(self, path):  # pragma: no cover - not used here
        raise NotImplementedError


def _write_yaml(directory: Path, name: str, payload: dict) -> Path:
    path = directory / f"{name}.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def _base_config(**overrides) -> dict:
    cfg = {
        "slug": "tala",
        "name": "Tala test",
        "kind": "municipal_portal",
        "municipality": "Tala",
        "official_url": "https://tala.example.test/index",
        "is_active": True,
        "scraper": {
            "type": "generic_http",
            "allowed_domains": ["tala.example.test", "files.example.test"],
            "document_extensions": ["pdf"],
            "documents": [
                {"url": "https://files.example.test/a.pdf", "title": "Doc A"},
                {"url": "https://files.example.test/b.pdf", "title": "Doc B"},
                {"url": "https://files.example.test/c.pdf", "title": "Doc C"},
                {"url": "https://evil.example.test/d.pdf", "title": "Bad domain"},
                {"url": "https://files.example.test/e.exe", "title": "Bad ext"},
            ],
        },
    }
    cfg.update(overrides)
    return cfg


@pytest.fixture
def sources_dir(tmp_path: Path, monkeypatch):
    def _find(slug: str):
        return source_loader_mod.find_source_config(slug, directory=tmp_path)

    monkeypatch.setattr(ingest_source_mod, "find_source_config", _find)
    return tmp_path


def _build_use_case():
    return (
        IngestSourceUseCase(
            source_repo=_InMemorySourceRepo(),
            document_repo=_InMemoryDocRepo(),
            raw_storage=_RecordingRawStorage(),
        ),
        _InMemoryDocRepo,
    )


def test_dry_run_returns_planned_urls_without_network(sources_dir: Path):
    _write_yaml(sources_dir, "tala", _base_config())
    use_case, _ = _build_use_case()

    result = use_case.execute("tala", limit=5, dry_run=True)

    assert result.dry_run is True
    assert result.documents_seen == 3  # 3 valid (a, b, c); d and e rejected
    assert result.documents_skipped == 2
    assert result.direct_urls == [
        "https://files.example.test/a.pdf",
        "https://files.example.test/b.pdf",
        "https://files.example.test/c.pdf",
    ]
    assert result.planned_urls == result.direct_urls
    assert result.discovered_urls == []
    assert result.seed_urls_checked == []
    assert result.documents_inserted == 0
    # Skip reasons live in `skipped_urls` (structured), not `errors`.
    reasons = [s["reason"] for s in result.skipped_urls]
    assert any("domain_not_allowed" in r for r in reasons)
    assert any(r == "extension_not_allowed" for r in reasons)
    assert result.errors == []


def test_dry_run_respects_limit(sources_dir: Path):
    _write_yaml(sources_dir, "tala", _base_config())
    use_case, _ = _build_use_case()

    result = use_case.execute("tala", limit=2, dry_run=True)

    assert result.documents_seen == 2
    assert len(result.planned_urls) == 2


def test_dry_run_does_not_touch_storage_or_db(sources_dir: Path):
    _write_yaml(sources_dir, "tala", _base_config())
    source_repo = _InMemorySourceRepo()
    doc_repo = _InMemoryDocRepo()
    raw = _RecordingRawStorage()
    use_case = IngestSourceUseCase(
        source_repo=source_repo,
        document_repo=doc_repo,
        raw_storage=raw,
    )

    use_case.execute("tala", limit=5, dry_run=True)

    assert source_repo._by_slug == {}
    assert doc_repo.inserted == []
    assert raw.stored == []


def test_placeholder_official_url_raises(sources_dir: Path):
    cfg = _base_config(official_url="https://example.invalid/REEMPLAZAR")
    _write_yaml(sources_dir, "tala", cfg)
    use_case, _ = _build_use_case()

    with pytest.raises(PlaceholderUrlError, match="placeholder official_url"):
        use_case.execute("tala", limit=5, dry_run=True)


def test_placeholder_document_url_raises(sources_dir: Path):
    cfg = _base_config()
    cfg["scraper"]["documents"].append(
        {"url": "https://example.invalid/bad.pdf"}
    )
    _write_yaml(sources_dir, "tala", cfg)
    use_case, _ = _build_use_case()

    with pytest.raises(PlaceholderUrlError, match="placeholder document URL"):
        use_case.execute("tala", limit=5, dry_run=True)


def test_limit_must_be_positive(sources_dir: Path):
    _write_yaml(sources_dir, "tala", _base_config())
    use_case, _ = _build_use_case()

    with pytest.raises(ValueError, match="limit must be a positive integer"):
        use_case.execute("tala", limit=0, dry_run=True)


# ---------------------------------------------------------------------
# Seed-URL flow: dry-run fetches the seed HTML (cheap) and reports
# discovered links without downloading the documents themselves.
# ---------------------------------------------------------------------


_SEED_HTML = """
<html><body>
  <a href="/docs/x.pdf">X</a>
  <a href="/docs/y.pdf">Y</a>
  <a href="/styles.css">asset</a>
</body></html>
"""


def _seed_config() -> dict:
    return {
        "slug": "tala",
        "name": "Tala test",
        "kind": "municipal_portal",
        "municipality": "Tala",
        "official_url": "https://tala.example.test/index",
        "is_active": True,
        "scraper": {
            "type": "generic_http",
            "allowed_domains": ["tala.example.test"],
            "document_extensions": ["pdf"],
            "seed_urls": ["https://tala.example.test/index"],
            "direct_documents": [
                {"url": "https://tala.example.test/manual.pdf", "title": "Manual"},
            ],
        },
    }


def test_dry_run_with_seed_urls_discovers_links(sources_dir: Path, monkeypatch):
    """Use case wires the scraper.plan() output into IngestionResult fields."""
    from open_data_jalisco.ingestion import ingest_source as ingest_mod
    from open_data_jalisco.adapters.scrapers.generic_http import GenericHttpScraper

    _write_yaml(sources_dir, "tala", _seed_config())

    # Replace build_scraper so we control the html_fetcher. This is the same
    # symbol the use case imports.
    def fake_build_scraper(scraper_cfg, *, timeout=None, user_agent=None):
        return GenericHttpScraper(
            user_agent=user_agent,
            timeout=timeout,
            html_fetcher=lambda url: _SEED_HTML,
        )

    monkeypatch.setattr(ingest_mod, "build_scraper", fake_build_scraper)

    use_case, _ = _build_use_case()
    result = use_case.execute("tala", limit=10, dry_run=True)

    assert result.dry_run is True
    assert result.direct_urls == ["https://tala.example.test/manual.pdf"]
    assert result.seed_urls_checked == ["https://tala.example.test/index"]
    assert "https://tala.example.test/docs/x.pdf" in result.discovered_urls
    assert "https://tala.example.test/docs/y.pdf" in result.discovered_urls
    # planned_urls = direct first, then discovered.
    assert result.planned_urls[0] == "https://tala.example.test/manual.pdf"
    assert set(result.planned_urls[1:]) == {
        "https://tala.example.test/docs/x.pdf",
        "https://tala.example.test/docs/y.pdf",
    }
    assert result.documents_seen == 3
    # asset_extension reason should be present (styles.css)
    assert any(s["reason"] == "asset_extension" for s in result.skipped_urls)
    # No DB / storage side effects.
    assert result.documents_inserted == 0
    assert result.errors == []


def test_dry_run_with_seed_does_not_fetch_documents(sources_dir: Path, monkeypatch):
    """Only the seed HTML may be fetched in dry-run; documents must not be."""
    from open_data_jalisco.ingestion import ingest_source as ingest_mod
    from open_data_jalisco.adapters.scrapers.generic_http import GenericHttpScraper

    _write_yaml(sources_dir, "tala", _seed_config())

    fetch_calls: list[str] = []
    html_fetch_calls: list[str] = []

    def fake_build_scraper(scraper_cfg, *, timeout=None, user_agent=None):
        scraper = GenericHttpScraper(
            user_agent=user_agent,
            timeout=timeout,
            html_fetcher=lambda url: (html_fetch_calls.append(url) or _SEED_HTML),
        )
        # Trap the document fetch path — must never be called in dry-run.
        def boom(url):
            fetch_calls.append(url)
            raise AssertionError(f"document fetch attempted in dry-run: {url}")
        scraper.fetch = boom  # type: ignore[assignment]
        return scraper

    monkeypatch.setattr(ingest_mod, "build_scraper", fake_build_scraper)

    use_case, _ = _build_use_case()
    result = use_case.execute("tala", limit=10, dry_run=True)

    assert fetch_calls == []                                  # zero document fetches
    assert html_fetch_calls == ["https://tala.example.test/index"]   # one seed fetch
    assert len(result.planned_urls) == 3


def test_dry_run_with_seed_respects_limit(sources_dir: Path, monkeypatch):
    from open_data_jalisco.ingestion import ingest_source as ingest_mod
    from open_data_jalisco.adapters.scrapers.generic_http import GenericHttpScraper

    _write_yaml(sources_dir, "tala", _seed_config())

    def fake_build_scraper(scraper_cfg, *, timeout=None, user_agent=None):
        return GenericHttpScraper(html_fetcher=lambda url: _SEED_HTML)

    monkeypatch.setattr(ingest_mod, "build_scraper", fake_build_scraper)

    use_case, _ = _build_use_case()
    result = use_case.execute("tala", limit=2, dry_run=True)

    # entries capped at 2 (direct first, then one discovered).
    assert len(result.planned_urls) == 2
    assert result.documents_seen == 2
    # discovered_urls still lists everything found (informational).
    assert len(result.discovered_urls) == 2


def test_placeholder_seed_url_raises(sources_dir: Path):
    cfg = _base_config()
    cfg["scraper"]["seed_urls"] = ["https://example.invalid/REEMPLAZAR"]
    _write_yaml(sources_dir, "tala", cfg)
    use_case, _ = _build_use_case()

    with pytest.raises(PlaceholderUrlError, match="placeholder seed_url"):
        use_case.execute("tala", limit=5, dry_run=True)


# ---------------------------------------------------------------------
# Year/month inference from URL paths like /content/2026/01/.../file.pdf
# ---------------------------------------------------------------------


def _config_with_inferable_url() -> dict:
    return {
        "slug": "tala",
        "name": "Tala test",
        "kind": "municipal_portal",
        "municipality": "Tala",
        "official_url": "https://tala.example.test/index",
        "is_active": True,
        "scraper": {
            "type": "generic_http",
            "allowed_domains": ["files.example.test"],
            "document_extensions": ["pdf"],
            "direct_documents": [
                {"url": "https://files.example.test/content/2026/01/3998/a.pdf"},
            ],
        },
    }


class _FakeScraper:
    """Returns a plan with one entry and a successful canned fetch."""

    def __init__(self, *, url: str, content: bytes = b"hello", explicit_year=None):
        self._url = url
        self._content = content
        self._explicit_year = explicit_year

    def plan(self, scraper_cfg, *, limit):
        from open_data_jalisco.ports.scraper import ScraperPlan, ScraperPlanEntry

        plan = ScraperPlan()
        plan.direct_urls = [self._url]
        plan.entries = [
            ScraperPlanEntry(
                url=self._url,
                source="direct",
                year=self._explicit_year,
            )
        ]
        return plan

    def fetch(self, url):
        return self._content, "application/pdf", "pdf"


def test_year_is_inferred_from_url_when_yaml_did_not_provide_one(
    sources_dir: Path, monkeypatch
):
    from open_data_jalisco.ingestion import ingest_source as ingest_mod

    _write_yaml(sources_dir, "tala", _config_with_inferable_url())
    url = "https://files.example.test/content/2026/01/3998/a.pdf"

    def fake_build_scraper(scraper_cfg, *, timeout=None, user_agent=None):
        return _FakeScraper(url=url)

    monkeypatch.setattr(ingest_mod, "build_scraper", fake_build_scraper)

    source_repo = _InMemorySourceRepo()
    doc_repo = _InMemoryDocRepo()
    raw = _RecordingRawStorage()
    use_case = IngestSourceUseCase(
        source_repo=source_repo,
        document_repo=doc_repo,
        raw_storage=raw,
    )

    result = use_case.execute("tala", limit=5, dry_run=False)

    assert result.documents_inserted == 1
    [doc] = doc_repo.inserted
    assert doc.year == 2026
    assert doc.metadata is not None
    assert doc.metadata.get("inferred_month") == 1
    assert doc.metadata.get("year_inferred_from_url") is True


def test_explicit_year_in_yaml_beats_url_inference(sources_dir: Path, monkeypatch):
    from open_data_jalisco.ingestion import ingest_source as ingest_mod

    _write_yaml(sources_dir, "tala", _config_with_inferable_url())
    url = "https://files.example.test/content/2026/01/3998/a.pdf"

    def fake_build_scraper(scraper_cfg, *, timeout=None, user_agent=None):
        # Simulate YAML having `year: 1999` for this entry.
        return _FakeScraper(url=url, explicit_year=1999)

    monkeypatch.setattr(ingest_mod, "build_scraper", fake_build_scraper)

    doc_repo = _InMemoryDocRepo()
    use_case = IngestSourceUseCase(
        source_repo=_InMemorySourceRepo(),
        document_repo=doc_repo,
        raw_storage=_RecordingRawStorage(),
    )

    use_case.execute("tala", limit=5, dry_run=False)

    [doc] = doc_repo.inserted
    assert doc.year == 1999
    # YAML provided year ⇒ no `year_inferred_from_url` flag added.
    assert (doc.metadata or {}).get("year_inferred_from_url") is None
    # But we still surface the URL month if present (it's independent of year).
    assert (doc.metadata or {}).get("inferred_month") == 1


def test_year_inference_no_metadata_changes_when_url_has_no_date(
    sources_dir: Path, monkeypatch
):
    from open_data_jalisco.ingestion import ingest_source as ingest_mod

    cfg = _config_with_inferable_url()
    cfg["scraper"]["direct_documents"] = [
        {"url": "https://files.example.test/no/dates/here.pdf"}
    ]
    _write_yaml(sources_dir, "tala", cfg)

    url = "https://files.example.test/no/dates/here.pdf"

    def fake_build_scraper(scraper_cfg, *, timeout=None, user_agent=None):
        return _FakeScraper(url=url)

    monkeypatch.setattr(ingest_mod, "build_scraper", fake_build_scraper)

    doc_repo = _InMemoryDocRepo()
    use_case = IngestSourceUseCase(
        source_repo=_InMemorySourceRepo(),
        document_repo=doc_repo,
        raw_storage=_RecordingRawStorage(),
    )

    use_case.execute("tala", limit=5, dry_run=False)

    [doc] = doc_repo.inserted
    assert doc.year is None
    # Without an inferable date the metadata stays clean.
    md = doc.metadata or {}
    assert "year_inferred_from_url" not in md
    assert "inferred_month" not in md

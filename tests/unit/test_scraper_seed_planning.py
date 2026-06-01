"""Tests for GenericHttpScraper.plan() — direct + seed combination, dedup, limit.

HTML is injected via the ``html_fetcher`` constructor parameter so these tests
make no network calls.
"""
from __future__ import annotations

from collections.abc import Callable

import pytest

from open_data_jalisco.adapters.scrapers.generic_http import GenericHttpScraper


_SEED_HTML = """
<html><body>
  <a href="/docs/a.pdf">A</a>
  <a href="/docs/b.pdf">B</a>
  <a href="/docs/c.xlsx">C XLSX</a>
  <a href="/img.png">asset</a>
  <a href="/page.html">html page</a>
  <a href="https://evil.example.com/x.pdf">off-domain</a>
</body></html>
"""


def _scraper_with_canned_html(html: str = _SEED_HTML) -> GenericHttpScraper:
    def fetcher(_url: str) -> str:
        return html

    return GenericHttpScraper(html_fetcher=fetcher)


def _scraper_with_failing_fetch(exc: Exception) -> GenericHttpScraper:
    def fetcher(_url: str) -> str:
        raise exc

    return GenericHttpScraper(html_fetcher=fetcher)


def test_direct_documents_only_no_seed():
    scraper = _scraper_with_canned_html(html="")
    config = {
        "slug": "test",
        "allowed_domains": ["tala.example.com"],
        "document_extensions": ["pdf"],
        "direct_documents": [
            {"url": "https://tala.example.com/d1.pdf", "title": "D1"},
            {"url": "https://tala.example.com/d2.pdf", "title": "D2"},
        ],
    }
    plan = scraper.plan(config, limit=10)

    assert plan.direct_urls == [
        "https://tala.example.com/d1.pdf",
        "https://tala.example.com/d2.pdf",
    ]
    assert plan.seed_urls_checked == []
    assert plan.discovered_urls == []
    assert [e.url for e in plan.entries] == plan.direct_urls
    assert [e.source for e in plan.entries] == ["direct", "direct"]
    assert plan.entries[0].title == "D1"


def test_seed_urls_discover_links():
    scraper = _scraper_with_canned_html()
    config = {
        "slug": "test",
        "allowed_domains": ["tala.example.com"],
        "document_extensions": ["pdf", "xlsx"],
        "seed_urls": ["https://tala.example.com/index.html"],
    }
    plan = scraper.plan(config, limit=10)

    assert plan.seed_urls_checked == ["https://tala.example.com/index.html"]
    assert "https://tala.example.com/docs/a.pdf" in plan.discovered_urls
    assert "https://tala.example.com/docs/b.pdf" in plan.discovered_urls
    assert "https://tala.example.com/docs/c.xlsx" in plan.discovered_urls
    assert plan.direct_urls == []
    # img.png, page.html, off-domain → skipped, with structured reasons.
    reasons = {s["reason"] for s in plan.skipped_urls}
    assert "asset_extension" in reasons
    assert "extension_not_allowed" in reasons
    assert any(r.startswith("domain_not_allowed") for r in reasons)


def test_plan_combines_direct_first_then_discovered():
    scraper = _scraper_with_canned_html()
    config = {
        "slug": "test",
        "allowed_domains": ["tala.example.com"],
        "document_extensions": ["pdf", "xlsx"],
        "direct_documents": [
            {"url": "https://tala.example.com/direct.pdf"},
        ],
        "seed_urls": ["https://tala.example.com/index.html"],
    }
    plan = scraper.plan(config, limit=10)

    urls = [e.url for e in plan.entries]
    sources = [e.source for e in plan.entries]
    assert urls[0] == "https://tala.example.com/direct.pdf"
    assert sources[0] == "direct"
    assert all(s == "discovered" for s in sources[1:])
    assert "https://tala.example.com/docs/a.pdf" in urls
    assert "https://tala.example.com/docs/b.pdf" in urls
    assert "https://tala.example.com/docs/c.xlsx" in urls


def test_plan_dedupes_when_direct_and_discovered_overlap():
    shared = "https://tala.example.com/docs/a.pdf"
    scraper = _scraper_with_canned_html()
    config = {
        "slug": "test",
        "allowed_domains": ["tala.example.com"],
        "document_extensions": ["pdf", "xlsx"],
        "direct_documents": [
            {"url": shared, "title": "From direct"},
        ],
        "seed_urls": ["https://tala.example.com/index.html"],
    }
    plan = scraper.plan(config, limit=10)

    urls = [e.url for e in plan.entries]
    assert urls.count(shared) == 1                # single entry
    assert shared in plan.direct_urls             # tagged as direct
    assert shared not in plan.discovered_urls     # not in discovered list
    assert plan.entries[0].title == "From direct"
    duplicate_skips = [s for s in plan.skipped_urls if s["reason"] == "duplicate"]
    assert any(s["url"] == shared for s in duplicate_skips)


def test_plan_limit_caps_entries_but_keeps_full_discovery_in_lists():
    scraper = _scraper_with_canned_html()
    config = {
        "slug": "test",
        "allowed_domains": ["tala.example.com"],
        "document_extensions": ["pdf", "xlsx"],
        "direct_documents": [
            {"url": "https://tala.example.com/d1.pdf"},
            {"url": "https://tala.example.com/d2.pdf"},
        ],
        "seed_urls": ["https://tala.example.com/index.html"],
    }
    plan = scraper.plan(config, limit=3)

    # The fetch list is capped at limit.
    assert len(plan.entries) == 3
    # First two entries are the direct ones (preserved order).
    urls = [e.url for e in plan.entries]
    assert urls[:2] == [
        "https://tala.example.com/d1.pdf",
        "https://tala.example.com/d2.pdf",
    ]
    # The reporting lists still expose the full picture (so the user can tune --limit).
    assert plan.direct_urls == [
        "https://tala.example.com/d1.pdf",
        "https://tala.example.com/d2.pdf",
    ]
    assert len(plan.discovered_urls) == 3   # a.pdf, b.pdf, c.xlsx all kept


def test_plan_handles_legacy_documents_key():
    scraper = _scraper_with_canned_html(html="")
    config = {
        "slug": "test",
        "allowed_domains": ["tala.example.com"],
        "document_extensions": ["pdf"],
        # Old YAML used `documents`; the scraper still accepts it.
        "documents": [
            {"url": "https://tala.example.com/legacy.pdf"},
        ],
    }
    plan = scraper.plan(config, limit=10)
    assert plan.direct_urls == ["https://tala.example.com/legacy.pdf"]


def test_direct_documents_takes_precedence_over_legacy_documents():
    scraper = _scraper_with_canned_html(html="")
    config = {
        "slug": "test",
        "allowed_domains": ["tala.example.com"],
        "document_extensions": ["pdf"],
        "direct_documents": [{"url": "https://tala.example.com/new.pdf"}],
        "documents": [{"url": "https://tala.example.com/old.pdf"}],
    }
    plan = scraper.plan(config, limit=10)
    assert plan.direct_urls == ["https://tala.example.com/new.pdf"]


def test_plan_records_seed_fetch_failure():
    scraper = _scraper_with_failing_fetch(RuntimeError("connection refused"))
    config = {
        "slug": "test",
        "allowed_domains": ["tala.example.com"],
        "document_extensions": ["pdf"],
        "seed_urls": ["https://tala.example.com/index.html"],
    }
    plan = scraper.plan(config, limit=5)

    assert plan.seed_urls_checked == ["https://tala.example.com/index.html"]
    assert plan.discovered_urls == []
    assert any(
        s["url"] == "https://tala.example.com/index.html"
        and s["reason"].startswith("seed_fetch_failed")
        for s in plan.skipped_urls
    )


def test_plan_rejects_invalid_direct_url():
    scraper = _scraper_with_canned_html(html="")
    config = {
        "slug": "test",
        "allowed_domains": ["tala.example.com"],
        "document_extensions": ["pdf"],
        "direct_documents": [
            {"url": "https://tala.example.com/ok.pdf"},
            {"url": "https://evil.com/leak.pdf"},                # bad domain
            {"url": "https://tala.example.com/script.js"},        # bad extension
            {"title": "Missing URL"},                             # no url
        ],
    }
    plan = scraper.plan(config, limit=10)

    assert plan.direct_urls == ["https://tala.example.com/ok.pdf"]
    assert len(plan.skipped_urls) == 3
    reasons = {s["reason"] for s in plan.skipped_urls}
    assert any(r.startswith("domain_not_allowed") for r in reasons)
    assert "extension_not_allowed" in reasons
    assert "missing_url_in_entry" in reasons


def test_plan_rejects_zero_or_negative_limit():
    scraper = _scraper_with_canned_html(html="")
    for bad in (0, -1, -100):
        with pytest.raises(ValueError, match="limit"):
            scraper.plan({}, limit=bad)


def test_plan_flags_seed_without_anchors_as_spa_candidate():
    """A seed that yields no anchors at all is most likely JS-rendered."""
    scraper = _scraper_with_canned_html(html="<html><body>no links here</body></html>")
    config = {
        "slug": "test",
        "allowed_domains": ["tala.example.com"],
        "document_extensions": ["pdf"],
        "seed_urls": ["https://tala.example.com/spa"],
    }
    plan = scraper.plan(config, limit=5)

    assert plan.discovered_urls == []
    assert any(
        s["url"] == "https://tala.example.com/spa"
        and s["reason"] == "seed_no_anchors_found"
        for s in plan.skipped_urls
    )


def test_plan_does_not_emit_no_anchors_when_links_were_filtered():
    """If links existed but were all filtered, the per-link reasons already say so."""
    html = """
    <a href="https://evil.com/x.pdf">bad domain</a>
    <a href="/file.exe">bad ext</a>
    """
    scraper = _scraper_with_canned_html(html=html)
    config = {
        "slug": "test",
        "allowed_domains": ["tala.example.com"],
        "document_extensions": ["pdf"],
        "seed_urls": ["https://tala.example.com/idx"],
    }
    plan = scraper.plan(config, limit=5)

    assert plan.discovered_urls == []
    # We have explicit per-link skips, so we should NOT also emit
    # seed_no_anchors_found (that signal is reserved for the SPA case).
    assert not any(
        s["reason"] == "seed_no_anchors_found" for s in plan.skipped_urls
    )


def test_plan_empty_config_returns_empty_plan():
    scraper = _scraper_with_canned_html(html="")
    plan = scraper.plan({"slug": "empty"}, limit=5)
    assert plan.direct_urls == []
    assert plan.discovered_urls == []
    assert plan.seed_urls_checked == []
    assert plan.entries == []
    assert plan.skipped_urls == []

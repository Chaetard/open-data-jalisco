"""Tests for SapumuContentScraper — plan() with content_pages, dedup, validation, limit.

HTML is injected via ``html_fetcher`` so no network calls happen.
"""
from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from open_data_jalisco.adapters.scrapers.sapumu_content import SapumuContentScraper


def _html_with_payload(payload: dict) -> str:
    encoded = json.dumps(payload).replace('"', "&quot;")
    return f'<html><body><level-content :content="{encoded}"></level-content></body></html>'


def _sample_payload_with_three_files() -> dict:
    return {
        "id": 63,
        "title": "Contenido 63",
        "grouped_media": [
            {
                "year": 2025,
                "months": [
                    {
                        "month": 11,
                        "files": [
                            {
                                "id": 2743,
                                "title": "Doc A",
                                "full_url": "https://files.example.com/2025/11/a.pdf",
                                "extension": "pdf",
                                "mime_type": "application/pdf",
                                "size": 1234,
                                "slug": "doc-a",
                                "date_at": "2025-11-15",
                                "file_name": "a.pdf",
                                # PII that must not appear in the entry:
                                "ip": "10.0.0.1",
                                "email": "x@example.gov",
                            },
                            {
                                "id": 2744,
                                "title": "Doc B",
                                "full_url": "https://files.example.com/2025/11/b.xlsx",
                                "extension": "xlsx",
                            },
                        ],
                    }
                ],
            },
            {
                "year": 2026,
                "months": [
                    {
                        "month": 1,
                        "files": [
                            {
                                "id": 4035,
                                "title": "Doc C",
                                "full_url": "https://files.example.com/2026/01/c.pdf",
                                "extension": "pdf",
                            }
                        ],
                    }
                ],
            },
        ],
    }


def _scraper(fetcher: Callable[[str], str]) -> SapumuContentScraper:
    return SapumuContentScraper(html_fetcher=fetcher)


def test_plan_discovers_files_from_content_page():
    payload = _sample_payload_with_three_files()
    scraper = _scraper(lambda _url: _html_with_payload(payload))
    config = {
        "slug": "tala",
        "allowed_domains": ["files.example.com"],
        "document_extensions": ["pdf", "xlsx"],
        "content_pages": ["https://tala.example.com/.../contenido/63"],
    }

    plan = scraper.plan(config, limit=10)

    assert plan.content_pages_checked == ["https://tala.example.com/.../contenido/63"]
    assert plan.direct_urls == []
    assert set(plan.discovered_urls) == {
        "https://files.example.com/2025/11/a.pdf",
        "https://files.example.com/2025/11/b.xlsx",
        "https://files.example.com/2026/01/c.pdf",
    }
    # All discovered, all in fetch list (under limit).
    assert len(plan.entries) == 3
    assert all(e.source == "discovered" for e in plan.entries)


def test_plan_entry_carries_safe_metadata_no_pii():
    scraper = _scraper(lambda _u: _html_with_payload(_sample_payload_with_three_files()))
    plan = scraper.plan(
        {
            "slug": "tala",
            "allowed_domains": ["files.example.com"],
            "document_extensions": ["pdf"],
            "content_pages": ["https://tala.example.com/c/63"],
        },
        limit=5,
    )
    # Find Doc A; its YAML upstream had ip/email which must not leak.
    doc_a = next(e for e in plan.entries if e.url.endswith("a.pdf"))
    assert doc_a.title == "Doc A"
    assert doc_a.year == 2025
    sapumu_meta = doc_a.metadata.get("sapumu") or {}
    assert sapumu_meta.get("content_id") == 63
    assert sapumu_meta.get("month") == 11
    assert sapumu_meta.get("file_id") == 2743
    # The PII fields must be entirely absent from the metadata.
    flat = json.dumps(doc_a.metadata)
    assert "10.0.0.1" not in flat
    assert "x@example.gov" not in flat
    assert "user_agent" not in flat
    assert "browser" not in flat
    assert "activities" not in flat


def test_plan_filters_by_allowed_domains():
    payload = {
        "id": 1,
        "title": "x",
        "grouped_media": [
            {
                "year": 2025,
                "months": [
                    {
                        "month": 1,
                        "files": [
                            {"full_url": "https://files.example.com/ok.pdf", "extension": "pdf"},
                            {"full_url": "https://evil.example.com/x.pdf", "extension": "pdf"},
                        ],
                    }
                ],
            }
        ],
    }
    scraper = _scraper(lambda _u: _html_with_payload(payload))
    plan = scraper.plan(
        {
            "slug": "t",
            "allowed_domains": ["files.example.com"],
            "document_extensions": ["pdf"],
            "content_pages": ["https://tala.example.com/c/1"],
        },
        limit=10,
    )
    assert plan.discovered_urls == ["https://files.example.com/ok.pdf"]
    reasons = [s["reason"] for s in plan.skipped_urls]
    assert any(r.startswith("domain_not_allowed") for r in reasons)


def test_plan_filters_by_document_extension():
    payload = {
        "id": 1,
        "title": "x",
        "grouped_media": [
            {
                "year": 2025,
                "months": [
                    {
                        "month": 1,
                        "files": [
                            {"full_url": "https://files.example.com/ok.pdf", "extension": "pdf"},
                            {"full_url": "https://files.example.com/bad.exe", "extension": "exe"},
                        ],
                    }
                ],
            }
        ],
    }
    scraper = _scraper(lambda _u: _html_with_payload(payload))
    plan = scraper.plan(
        {
            "slug": "t",
            "allowed_domains": ["files.example.com"],
            "document_extensions": ["pdf"],
            "content_pages": ["https://tala.example.com/c/1"],
        },
        limit=10,
    )
    assert plan.discovered_urls == ["https://files.example.com/ok.pdf"]
    assert any(s["reason"] == "extension_not_allowed" for s in plan.skipped_urls)


def test_plan_dedupes_direct_and_discovered():
    shared = "https://files.example.com/2025/11/a.pdf"
    payload = _sample_payload_with_three_files()  # contains shared as Doc A
    scraper = _scraper(lambda _u: _html_with_payload(payload))
    config = {
        "slug": "t",
        "allowed_domains": ["files.example.com"],
        "document_extensions": ["pdf", "xlsx"],
        "direct_documents": [{"url": shared, "title": "From direct"}],
        "content_pages": ["https://tala.example.com/c/63"],
    }
    plan = scraper.plan(config, limit=10)
    urls = [e.url for e in plan.entries]
    assert urls.count(shared) == 1
    # Direct version wins (kept as direct, marked direct).
    direct_entry = next(e for e in plan.entries if e.url == shared)
    assert direct_entry.source == "direct"
    assert direct_entry.title == "From direct"
    # The duplicate from discovery shows up as a skip.
    assert any(s["url"] == shared and s["reason"] == "duplicate" for s in plan.skipped_urls)


def test_plan_respects_limit_across_direct_and_discovered():
    scraper = _scraper(lambda _u: _html_with_payload(_sample_payload_with_three_files()))
    config = {
        "slug": "t",
        "allowed_domains": ["files.example.com"],
        "document_extensions": ["pdf", "xlsx"],
        "direct_documents": [
            {"url": "https://files.example.com/direct.pdf"},
        ],
        "content_pages": ["https://tala.example.com/c/63"],
    }
    plan = scraper.plan(config, limit=2)
    assert len(plan.entries) == 2
    # Direct first.
    assert plan.entries[0].url == "https://files.example.com/direct.pdf"
    assert plan.entries[0].source == "direct"
    # Then one discovered (the first file in document order).
    assert plan.entries[1].source == "discovered"


def test_plan_handles_multiple_content_pages():
    pages: dict[str, dict] = {
        "https://t.example.com/c/63": {
            "id": 63,
            "title": "C63",
            "grouped_media": [
                {
                    "year": 2025,
                    "months": [
                        {
                            "month": 11,
                            "files": [
                                {"full_url": "https://files.example.com/a.pdf", "extension": "pdf"}
                            ],
                        }
                    ],
                }
            ],
        },
        "https://t.example.com/c/64": {
            "id": 64,
            "title": "C64",
            "grouped_media": [
                {
                    "year": 2025,
                    "months": [
                        {
                            "month": 12,
                            "files": [
                                {"full_url": "https://files.example.com/b.pdf", "extension": "pdf"}
                            ],
                        }
                    ],
                }
            ],
        },
    }

    def fetcher(url: str) -> str:
        return _html_with_payload(pages[url])

    scraper = _scraper(fetcher)
    plan = scraper.plan(
        {
            "slug": "t",
            "allowed_domains": ["files.example.com"],
            "document_extensions": ["pdf"],
            "content_pages": list(pages.keys()),
        },
        limit=10,
    )

    assert plan.content_pages_checked == list(pages.keys())
    assert sorted(plan.discovered_urls) == [
        "https://files.example.com/a.pdf",
        "https://files.example.com/b.pdf",
    ]


def test_plan_records_no_level_content_when_html_lacks_tag():
    scraper = _scraper(lambda _u: "<html><body>nothing here</body></html>")
    plan = scraper.plan(
        {
            "slug": "t",
            "allowed_domains": [],
            "document_extensions": ["pdf"],
            "content_pages": ["https://t.example.com/c/1"],
        },
        limit=5,
    )
    assert plan.discovered_urls == []
    assert any(
        s["url"] == "https://t.example.com/c/1"
        and s["reason"] == "no_level_content_found"
        for s in plan.skipped_urls
    )


def test_plan_records_content_fetch_failure():
    def fail(_url: str) -> str:
        raise RuntimeError("HTTP 500")

    scraper = _scraper(fail)
    plan = scraper.plan(
        {
            "slug": "t",
            "allowed_domains": [],
            "document_extensions": ["pdf"],
            "content_pages": ["https://t.example.com/c/1"],
        },
        limit=5,
    )
    assert plan.discovered_urls == []
    assert any(
        s["url"] == "https://t.example.com/c/1"
        and s["reason"].startswith("content_fetch_failed")
        for s in plan.skipped_urls
    )


def test_plan_skips_files_without_full_url():
    payload = {
        "id": 1,
        "title": "x",
        "grouped_media": [
            {
                "year": 2025,
                "months": [
                    {
                        "month": 1,
                        "files": [
                            {"title": "no url", "extension": "pdf"},  # missing full_url
                            {"full_url": "https://files.example.com/ok.pdf", "extension": "pdf"},
                        ],
                    }
                ],
            }
        ],
    }
    scraper = _scraper(lambda _u: _html_with_payload(payload))
    plan = scraper.plan(
        {
            "slug": "t",
            "allowed_domains": ["files.example.com"],
            "document_extensions": ["pdf"],
            "content_pages": ["https://t.example.com/c/1"],
        },
        limit=5,
    )
    assert plan.discovered_urls == ["https://files.example.com/ok.pdf"]
    assert any(s["reason"] == "file_missing_full_url" for s in plan.skipped_urls)


def test_plan_rejects_zero_limit():
    scraper = _scraper(lambda _u: "")
    with pytest.raises(ValueError, match="limit"):
        scraper.plan({}, limit=0)

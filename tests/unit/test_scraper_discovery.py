# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Pure HTML link-discovery tests. No network, no scraper, no filesystem."""
from __future__ import annotations

from open_data_jalisco.adapters.scrapers._discovery import (
    ASSET_EXTENSIONS,
    extract_document_links,
)


_INDEX_HTML = """
<html>
<head><title>Index</title></head>
<body>
  <h1>Transparencia</h1>
  <ul>
    <li><a href="/docs/contract.pdf">Contract (relative)</a></li>
    <li><a href="https://files.example.com/budget.xlsx">Budget XLSX (absolute)</a></li>
    <li><a href="/docs/report.docx">Report DOCX</a></li>
    <li><a href="/about.html">About (html, not a doc)</a></li>
    <li><a href="/styles.css">CSS asset</a></li>
    <li><a href="https://cdn.example.com/banner.png">PNG asset</a></li>
    <li><a href="mailto:transparencia@example.com">Email</a></li>
    <li><a href="#section-2">Anchor</a></li>
    <li><a href="javascript:void(0)">JS</a></li>
    <li><a href="ftp://example.com/file.pdf">FTP (non-http)</a></li>
    <li><a href="https://evil.com/leak.pdf">Off-domain</a></li>
    <li><a href="/docs/contract.pdf">Duplicate contract</a></li>
    <li><a href="/docs/data.pdf#page=3">PDF with fragment</a></li>
  </ul>
</body>
</html>
"""

_BASE = "https://tala.example.com/transparencia/articulo-8"


def test_extracts_and_resolves_relative_urls():
    kept, _ = extract_document_links(
        _INDEX_HTML,
        _BASE,
        allowed_domains=["tala.example.com", "files.example.com"],
        document_extensions=["pdf", "xlsx", "docx"],
    )
    assert "https://tala.example.com/docs/contract.pdf" in kept
    assert "https://files.example.com/budget.xlsx" in kept
    assert "https://tala.example.com/docs/report.docx" in kept


def test_strips_url_fragment():
    kept, _ = extract_document_links(
        _INDEX_HTML,
        _BASE,
        allowed_domains=["tala.example.com"],
        document_extensions=["pdf"],
    )
    assert "https://tala.example.com/docs/data.pdf" in kept
    # fragment must NOT remain in the kept URL
    assert all("#" not in u for u in kept)


def test_dedupes_within_html():
    kept, _ = extract_document_links(
        _INDEX_HTML,
        _BASE,
        allowed_domains=["tala.example.com"],
        document_extensions=["pdf"],
    )
    assert kept.count("https://tala.example.com/docs/contract.pdf") == 1


def test_filters_by_allowed_domains():
    _kept, skipped = extract_document_links(
        _INDEX_HTML,
        _BASE,
        allowed_domains=["tala.example.com"],
        document_extensions=["pdf", "xlsx"],
    )
    off_domain = [s for s in skipped if "evil.com" in s["url"]]
    assert off_domain
    assert off_domain[0]["reason"].startswith("domain_not_allowed")
    files_subdomain = [s for s in skipped if "files.example.com" in s["url"]]
    assert files_subdomain
    assert files_subdomain[0]["reason"].startswith("domain_not_allowed")


def test_filters_by_document_extension():
    _kept, skipped = extract_document_links(
        _INDEX_HTML,
        _BASE,
        allowed_domains=None,
        document_extensions=["pdf"],
    )
    xlsx = [s for s in skipped if s["url"].endswith(".xlsx")]
    assert xlsx
    assert xlsx[0]["reason"] == "extension_not_allowed"
    docx = [s for s in skipped if s["url"].endswith(".docx")]
    assert docx
    assert docx[0]["reason"] == "extension_not_allowed"


def test_skips_asset_extensions_even_without_doc_filter():
    _kept, skipped = extract_document_links(
        _INDEX_HTML,
        _BASE,
        allowed_domains=None,
        document_extensions=None,
    )
    reasons = {(s["url"], s["reason"]) for s in skipped}
    assert any(url.endswith(".css") and reason == "asset_extension" for url, reason in reasons)
    assert any(url.endswith(".png") and reason == "asset_extension" for url, reason in reasons)


def test_skips_non_http_schemes():
    _kept, skipped = extract_document_links(
        _INDEX_HTML,
        _BASE,
        allowed_domains=None,
        document_extensions=None,
    )
    ftp = [s for s in skipped if s["url"].startswith("ftp:")]
    assert ftp
    assert ftp[0]["reason"] == "non_http_scheme"


def test_silently_ignores_anchors_mailto_and_js():
    """These hrefs are uninteresting noise, not failures — don't pollute skipped_urls."""
    _kept, skipped = extract_document_links(
        _INDEX_HTML,
        _BASE,
        allowed_domains=None,
        document_extensions=None,
    )
    urls = [s["url"] for s in skipped]
    assert not any(u.startswith("mailto:") for u in urls)
    assert not any(u.startswith("javascript:") for u in urls)
    assert not any(u == "#section-2" for u in urls)


def test_extensionless_url_rejected_when_doc_extensions_set():
    html = '<a href="/docs/page">No extension</a>'
    _kept, skipped = extract_document_links(
        html,
        "https://example.com/",
        allowed_domains=None,
        document_extensions=["pdf"],
    )
    assert any(s["reason"] == "no_extension" for s in skipped)


def test_extensionless_url_rejected_when_no_filters():
    """Without doc-extensions config, we still refuse extensionless links."""
    html = '<a href="/docs/page">No extension</a>'
    _kept, skipped = extract_document_links(
        html,
        "https://example.com/",
        allowed_domains=None,
        document_extensions=None,
    )
    assert any(s["reason"] == "no_extension" for s in skipped)


def test_empty_html_returns_empty():
    assert extract_document_links(
        "",
        "https://example.com/",
        allowed_domains=None,
        document_extensions=["pdf"],
    ) == ([], [])


def test_asset_extension_set_is_reasonable():
    # Sanity: a few well-known assets are in the denylist.
    for ext in ("css", "js", "png", "jpg", "webp", "svg"):
        assert ext in ASSET_EXTENSIONS

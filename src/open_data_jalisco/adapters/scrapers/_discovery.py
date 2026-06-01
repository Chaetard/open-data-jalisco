# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Pure HTML link discovery for shallow seed pages.

No network. No I/O. Given an HTML string and a base URL, returns the set of
absolute URLs worth ingesting, plus a structured list of skip reasons.

This module is shared between the scraper (real ingest) and the use case
(dry-run reporting) so that both apply identical filtering rules.
"""
from __future__ import annotations

from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

# Common web asset extensions we never want to ingest as documents.
ASSET_EXTENSIONS: frozenset[str] = frozenset(
    {
        # styles, scripts, sourcemaps
        "css",
        "js",
        "mjs",
        "map",
        # images
        "png",
        "jpg",
        "jpeg",
        "gif",
        "webp",
        "svg",
        "ico",
        "bmp",
        "tiff",
        # fonts
        "woff",
        "woff2",
        "ttf",
        "eot",
        "otf",
        # av
        "mp4",
        "mp3",
        "avi",
        "mov",
        "webm",
        "wav",
        "ogg",
    }
)

# href schemes/prefixes we silently ignore (not recorded in skipped_urls).
_UNINTERESTING_PREFIXES: tuple[str, ...] = (
    "#",
    "mailto:",
    "tel:",
    "javascript:",
    "data:",
)


def _url_extension(path: str) -> str:
    """Lower-cased extension without dot, or '' if none."""
    last = path.rsplit("/", 1)[-1]
    if "." not in last:
        return ""
    return last.rsplit(".", 1)[-1].lower()


def extract_document_links(
    html: str,
    base_url: str,
    *,
    allowed_domains: list[str] | None = None,
    document_extensions: list[str] | None = None,
    asset_extensions: frozenset[str] = ASSET_EXTENSIONS,
) -> tuple[list[str], list[dict[str, str]]]:
    """Pull document-worthy links from ``html``.

    Returns ``(kept, skipped)``.

    - ``kept`` is the deduplicated list of absolute URLs that passed all
      filters, in document order.
    - ``skipped`` is a list of ``{"url": "...", "reason": "..."}`` dicts.
      Anchors, mailto/tel/javascript hrefs and bare ``#`` fragments are
      silently dropped (not recorded).

    Filters applied (in order):
        1. ``http(s)`` scheme only (else reason ``non_http_scheme``).
        2. Extension not in ``asset_extensions`` (else ``asset_extension``).
        3. Host in ``allowed_domains`` if it's non-empty (else
           ``domain_not_allowed:<host>``).
        4. Extension in ``document_extensions`` if it's non-empty (else
           ``extension_not_allowed``); if empty, an extensionless URL is
           rejected as ``no_extension``.
    """
    if not html:
        return [], []

    soup = BeautifulSoup(html, "lxml")

    kept: list[str] = []
    seen: set[str] = set()
    skipped: list[dict[str, str]] = []

    normalized_allowed = {d.lower() for d in (allowed_domains or [])}
    normalized_doc_ext = {e.lower().lstrip(".") for e in (document_extensions or [])}

    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(_UNINTERESTING_PREFIXES):
            continue

        absolute = urljoin(base_url, href).split("#", 1)[0]
        if not absolute or absolute in seen:
            continue
        seen.add(absolute)

        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            skipped.append({"url": absolute, "reason": "non_http_scheme"})
            continue

        ext = _url_extension(parsed.path)

        if ext in asset_extensions:
            skipped.append({"url": absolute, "reason": "asset_extension"})
            continue

        if normalized_allowed and parsed.netloc.lower() not in normalized_allowed:
            skipped.append(
                {"url": absolute, "reason": f"domain_not_allowed:{parsed.netloc.lower()}"}
            )
            continue

        if normalized_doc_ext:
            if not ext:
                skipped.append({"url": absolute, "reason": "no_extension"})
                continue
            if ext not in normalized_doc_ext:
                skipped.append({"url": absolute, "reason": "extension_not_allowed"})
                continue
        elif not ext:
            # No explicit allow-list: refuse extensionless URLs so we don't
            # ingest every navigational link on the page as a "document".
            skipped.append({"url": absolute, "reason": "no_extension"})
            continue

        kept.append(absolute)

    return kept, skipped

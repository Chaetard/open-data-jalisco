# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Reusable URL validation for scraper configs.

Shared between the actual scraper (which uses it to skip URLs before fetching)
and the ingestion use case (which uses it in dry-run mode to report what
would happen, without touching the network).
"""
from __future__ import annotations

from urllib.parse import urlparse


def is_url_allowed(
    url: str,
    *,
    allowed_domains: list[str] | None,
    document_extensions: list[str] | None,
) -> tuple[bool, str]:
    """Validate ``url`` against allow-lists.

    Returns ``(allowed, reason)``. ``reason`` is a short tag suitable for
    structured logging when ``allowed`` is False; empty string otherwise.

    - ``allowed_domains``: if non-empty, the URL's host must match one entry
      exactly. ``None`` or ``[]`` disables the check.
    - ``document_extensions``: if non-empty, the URL's path must end with
      one of the extensions (compared case-insensitively, without the dot).
      ``None`` or ``[]`` disables the check.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False, f"malformed_url:{url!r}"

    if allowed_domains:
        host = parsed.netloc.lower()
        normalized = {d.lower() for d in allowed_domains}
        if host not in normalized:
            return False, f"domain_not_allowed:{host}"

    if document_extensions:
        path = parsed.path.lower()
        normalized_ext = {e.lower().lstrip(".") for e in document_extensions}
        if not any(path.endswith("." + ext) for ext in normalized_ext):
            return False, "extension_not_allowed"

    return True, ""

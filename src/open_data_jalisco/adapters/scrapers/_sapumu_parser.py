# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Pure parser for SAPUMU content pages (Laravel/Vue Blade).

A SAPUMU content page embeds its document list inside a Vue component::

    <level-content :content="<HTML-escaped JSON>">

This module:
1. Locates that tag.
2. Decodes HTML entities and parses the JSON payload.
3. Walks ``content.grouped_media[].months[].files[]`` and yields a projected,
   *safe* subset of each file's fields.

It does **no** I/O, takes only an HTML string as input. The scraper and the
``sapumu scan-content`` CLI command share this module.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from html import unescape
from typing import Any

from bs4 import BeautifulSoup

# Fields we copy verbatim from the upstream `file` object. Anything else is
# either derived (year/month/content_*) or intentionally dropped.
_SAFE_FILE_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "title",
        "slug",
        "date_at",
        "name",
        "file_name",
        "mime_type",
        "size",
        "full_url",
        "extension",
        "created_at",
        "updated_at",
    }
)

# Fields we explicitly never copy — sensitive PII or noisy audit metadata.
# Listed for documentation and for the "no sensitive fields leak" test.
_BLOCKED_FILE_FIELDS: frozenset[str] = frozenset(
    {
        "activities",
        "causer",
        "causer_id",
        "causer_type",
        "user",
        "user_id",
        "email",
        "ip",
        "ip_address",
        "browser",
        "device",
        "user_agent",
        "extra_details",
        "properties",
    }
)


def extract_level_content_json(html: str) -> dict[str, Any] | None:
    """Return the JSON payload from the first ``<level-content :content="...">``
    tag in ``html``, or ``None`` if no such tag is present or the payload is
    not a JSON object.

    BeautifulSoup's parser already decodes HTML entities in attribute values
    (``&quot;`` → ``"``). We additionally try ``html.unescape`` as a fallback
    in case the upstream double-escapes.
    """
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("level-content")
    if tag is None:
        return None
    raw = tag.get(":content")
    if not raw:
        return None
    # Try the value as-is first, then with one extra unescape round.
    for candidate in (raw, unescape(raw)):
        try:
            data = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(data, dict):
            return data
    return None


def iter_files_from_content(content: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Walk ``content.grouped_media[].months[].files[]`` yielding cleaned
    file dicts.

    Each yielded dict contains only ``_SAFE_FILE_FIELDS`` plus derived keys:
    ``year`` (from grouped_media), ``month`` (from months), ``content_id``
    and ``content_title`` (from the outer content object).
    """
    if not isinstance(content, dict):
        return
    content_id = content.get("id")
    content_title = content.get("title")
    for group in content.get("grouped_media") or []:
        if not isinstance(group, dict):
            continue
        year = group.get("year")
        for month_obj in group.get("months") or []:
            if not isinstance(month_obj, dict):
                continue
            month = month_obj.get("month")
            for file in month_obj.get("files") or []:
                if not isinstance(file, dict):
                    continue
                yield _clean_file_entry(
                    file,
                    content_id=content_id,
                    content_title=content_title,
                    year=year,
                    month=month,
                )


def _clean_file_entry(
    file: dict[str, Any],
    *,
    content_id: Any,
    content_title: Any,
    year: Any,
    month: Any,
) -> dict[str, Any]:
    cleaned = {k: file[k] for k in _SAFE_FILE_FIELDS if k in file}
    cleaned["year"] = year
    cleaned["month"] = month
    cleaned["content_id"] = content_id
    cleaned["content_title"] = content_title
    return cleaned

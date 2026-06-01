# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Best-effort metadata inference from document URLs.

Currently extracts ``(year, month)`` from path segments of the form
``/YYYY/MM/`` — common in bucket layouts like
``/content/2026/01/3998/file.xlsx``. Pure, no I/O.
"""
from __future__ import annotations

import re

# Matches a /YYYY/M(M)/ segment. Anchored to slashes so we don't latch onto
# random 4-digit substrings (port numbers, IDs, etc).
_DATE_PATH_RE = re.compile(r"/(?P<year>\d{4})/(?P<month>\d{1,2})/")

# Inclusive range used to reject obvious noise (e.g. /9999/13/).
_MIN_YEAR = 1900
_MAX_YEAR = 2200


def infer_year_month_from_url(url: str | None) -> tuple[int | None, int | None]:
    """Return ``(year, month)`` if the URL contains a plausible ``/YYYY/MM/``
    segment, else ``(None, None)``.

    Picks the **first** match in the path, so e.g.
    ``/archive/2025/12/v2/2024/03/file.pdf`` infers ``(2025, 12)``.
    """
    if not url:
        return None, None
    for match in _DATE_PATH_RE.finditer(url):
        year = int(match.group("year"))
        month = int(match.group("month"))
        if _MIN_YEAR <= year <= _MAX_YEAR and 1 <= month <= 12:
            return year, month
    return None, None

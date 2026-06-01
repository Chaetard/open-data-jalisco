# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Pure tests for URL → (year, month) inference."""
from __future__ import annotations

import pytest

from open_data_jalisco.ingestion._url_inference import infer_year_month_from_url


@pytest.mark.parametrize(
    "url, expected",
    [
        (
            "https://app-sapumu.sfo2.digitaloceanspaces.com/tala/content/2026/01/3998/file.xlsx",
            (2026, 1),
        ),
        (
            "https://example.com/content/2025/12/abc/file.pdf",
            (2025, 12),
        ),
        (
            "https://example.com/2024/3/single-digit-month/file.pdf",
            (2024, 3),
        ),
        (
            # First match wins when multiple /YYYY/MM/ segments appear.
            "https://example.com/archive/2025/12/v2/2024/03/file.pdf",
            (2025, 12),
        ),
    ],
)
def test_extracts_year_and_month(url: str, expected: tuple[int, int]):
    assert infer_year_month_from_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/no/dates/here/file.pdf",
        "https://example.com/9999/13/file.pdf",        # month out of range
        "https://example.com/1899/06/file.pdf",        # year out of allowed range
        "https://example.com/2025/00/file.pdf",        # month=0
        "https://example.com/2025/13/file.pdf",        # month>12
        "",
    ],
)
def test_returns_none_when_no_valid_date(url: str):
    assert infer_year_month_from_url(url) == (None, None)


def test_none_url_returns_none_pair():
    assert infer_year_month_from_url(None) == (None, None)


def test_only_year_no_month_returns_none():
    # /2025/ alone isn't /YYYY/MM/ so we don't fabricate a month.
    assert infer_year_month_from_url("https://example.com/2025/file.pdf") == (None, None)


def test_ignores_4digit_in_query_string():
    # The regex anchors on slashes, so query params shouldn't trigger false positives.
    url = "https://example.com/path?year=2025&month=01"
    assert infer_year_month_from_url(url) == (None, None)

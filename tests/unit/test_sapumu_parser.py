"""Pure tests for the SAPUMU `<level-content :content="...">` parser."""
from __future__ import annotations

import json

from open_data_jalisco.adapters.scrapers._sapumu_parser import (
    _BLOCKED_FILE_FIELDS,
    _SAFE_FILE_FIELDS,
    extract_level_content_json,
    iter_files_from_content,
)


def _build_html(content_payload: dict) -> str:
    """Wrap a payload as a `<level-content :content="...">` tag inside HTML."""
    encoded = json.dumps(content_payload).replace('"', "&quot;")
    return f"""
    <html><body>
      <div class="header">Some text</div>
      <level-content :content="{encoded}"></level-content>
      <div class="footer">More text</div>
    </body></html>
    """


def _sample_payload() -> dict:
    return {
        "id": 63,
        "title": "Contenido 63 — Reglamentos",
        "slug": "reglamentos",
        "grouped_media": [
            {
                "year": 2025,
                "months": [
                    {
                        "month": 11,
                        "files": [
                            {
                                "id": 2743,
                                "title": "Documento A",
                                "slug": "doc-a",
                                "date_at": "2025-11-15",
                                "name": "A",
                                "file_name": "doc-a.pdf",
                                "mime_type": "application/pdf",
                                "size": 12345,
                                "full_url": "https://files.example.com/2025/11/2743/a.pdf",
                                "extension": "pdf",
                                "created_at": "2025-11-15T10:00:00Z",
                                "updated_at": "2025-11-15T10:00:00Z",
                                # noise / PII that must be stripped:
                                "causer": {"id": 7, "name": "admin"},
                                "causer_id": 7,
                                "causer_type": "App\\Models\\User",
                                "email": "admin@example.gov",
                                "ip": "10.0.0.1",
                                "ip_address": "10.0.0.1",
                                "browser": "Chrome 119",
                                "device": "desktop",
                                "user_agent": "Mozilla/5.0 ...",
                                "activities": [{"id": 1, "log_name": "media"}],
                                "extra_details": {"foo": "bar"},
                            }
                        ],
                    },
                    {
                        "month": 12,
                        "files": [
                            {
                                "id": 3700,
                                "title": "Documento B",
                                "full_url": "https://files.example.com/2025/12/3700/b.xlsx",
                                "mime_type": "application/vnd.openxml...",
                                "extension": "xlsx",
                            }
                        ],
                    },
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
                                "title": "Documento C",
                                "full_url": "https://files.example.com/2026/01/4035/c.pdf",
                                "extension": "pdf",
                            }
                        ],
                    }
                ],
            },
        ],
    }


def test_extracts_json_payload_from_level_content_tag():
    html = _build_html(_sample_payload())
    data = extract_level_content_json(html)
    assert data is not None
    assert data["id"] == 63
    assert data["title"] == "Contenido 63 — Reglamentos"


def test_returns_none_when_tag_absent():
    html = "<html><body>no level-content here</body></html>"
    assert extract_level_content_json(html) is None


def test_returns_none_when_attribute_empty():
    html = '<html><body><level-content :content=""></level-content></body></html>'
    assert extract_level_content_json(html) is None


def test_returns_none_when_attribute_not_json_object():
    html = '<html><body><level-content :content="not json"></level-content></body></html>'
    assert extract_level_content_json(html) is None


def test_returns_none_when_json_is_not_an_object():
    """A bare array isn't a content dict; refuse."""
    html = (
        '<html><body><level-content :content="[1,2,3]"></level-content></body></html>'
    )
    assert extract_level_content_json(html) is None


def test_handles_double_escaped_entities():
    """Some servers double-escape; we should recover."""
    payload = {"id": 1, "title": "x", "grouped_media": []}
    raw = json.dumps(payload)
    # Double-escape quotes: " → &quot; → &amp;quot;
    raw_escaped = raw.replace('"', "&amp;quot;")
    html = f'<level-content :content="{raw_escaped}"></level-content>'
    data = extract_level_content_json(html)
    assert data is not None
    assert data["id"] == 1


def test_empty_html_returns_none():
    assert extract_level_content_json("") is None


def test_iter_files_walks_grouped_media():
    payload = _sample_payload()
    files = list(iter_files_from_content(payload))
    assert len(files) == 3
    urls = {f["full_url"] for f in files}
    assert urls == {
        "https://files.example.com/2025/11/2743/a.pdf",
        "https://files.example.com/2025/12/3700/b.xlsx",
        "https://files.example.com/2026/01/4035/c.pdf",
    }


def test_iter_files_strips_sensitive_fields():
    payload = _sample_payload()
    files = list(iter_files_from_content(payload))
    first = files[0]
    for blocked in _BLOCKED_FILE_FIELDS:
        assert blocked not in first, f"sensitive field leaked: {blocked}"


def test_iter_files_only_carries_safe_fields_plus_derived():
    payload = _sample_payload()
    files = list(iter_files_from_content(payload))
    expected_keys = set(_SAFE_FILE_FIELDS) | {
        "year",
        "month",
        "content_id",
        "content_title",
    }
    for f in files:
        # No keys outside the safe + derived set.
        extras = set(f.keys()) - expected_keys
        assert not extras, f"unexpected fields: {extras}"


def test_iter_files_attaches_derived_year_month_and_content():
    payload = _sample_payload()
    files = list(iter_files_from_content(payload))
    by_id = {f["id"]: f for f in files}

    assert by_id[2743]["year"] == 2025
    assert by_id[2743]["month"] == 11
    assert by_id[2743]["content_id"] == 63
    assert by_id[2743]["content_title"] == "Contenido 63 — Reglamentos"

    assert by_id[3700]["year"] == 2025
    assert by_id[3700]["month"] == 12

    assert by_id[4035]["year"] == 2026
    assert by_id[4035]["month"] == 1


def test_iter_files_handles_missing_grouped_media():
    files = list(iter_files_from_content({"id": 1, "title": "x"}))
    assert files == []


def test_iter_files_handles_non_dict_input():
    assert list(iter_files_from_content(None)) == []
    assert list(iter_files_from_content("not a dict")) == []


def test_iter_files_skips_malformed_groups():
    """Groups/months/files that aren't dicts must not crash the walk."""
    payload = {
        "id": 1,
        "title": "x",
        "grouped_media": [
            "garbage",                                    # not a dict
            {"year": 2025, "months": "also garbage"},     # months not a list
            {
                "year": 2025,
                "months": [
                    "garbage",
                    {"month": 1, "files": None},
                    {
                        "month": 2,
                        "files": [
                            "garbage",
                            {"full_url": "https://e.com/ok.pdf", "extension": "pdf"},
                        ],
                    },
                ],
            },
        ],
    }
    files = list(iter_files_from_content(payload))
    assert len(files) == 1
    assert files[0]["full_url"] == "https://e.com/ok.pdf"


def test_iter_files_yields_empty_when_files_list_missing():
    payload = {
        "id": 1,
        "title": "x",
        "grouped_media": [{"year": 2025, "months": [{"month": 11}]}],  # no files
    }
    assert list(iter_files_from_content(payload)) == []

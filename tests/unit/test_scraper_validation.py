# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from open_data_jalisco.adapters.scrapers._validation import is_url_allowed


def test_no_lists_allow_everything():
    ok, reason = is_url_allowed(
        "https://example.com/a.pdf",
        allowed_domains=None,
        document_extensions=None,
    )
    assert ok is True
    assert reason == ""


def test_domain_allow_list_matches_host():
    ok, _ = is_url_allowed(
        "https://example.com/a.pdf",
        allowed_domains=["example.com"],
        document_extensions=None,
    )
    assert ok


def test_domain_allow_list_rejects_other_host():
    ok, reason = is_url_allowed(
        "https://evil.com/a.pdf",
        allowed_domains=["example.com"],
        document_extensions=None,
    )
    assert not ok
    assert reason.startswith("domain_not_allowed")


def test_extension_allow_list_matches():
    ok, _ = is_url_allowed(
        "https://example.com/path/file.PDF",
        allowed_domains=None,
        document_extensions=["pdf"],
    )
    assert ok


def test_extension_allow_list_rejects_other_extension():
    ok, reason = is_url_allowed(
        "https://example.com/file.exe",
        allowed_domains=None,
        document_extensions=["pdf"],
    )
    assert not ok
    assert reason == "extension_not_allowed"


def test_malformed_url_rejected():
    ok, reason = is_url_allowed(
        "not-a-url",
        allowed_domains=None,
        document_extensions=None,
    )
    assert not ok
    assert reason.startswith("malformed_url")


def test_both_filters_combined():
    ok, _ = is_url_allowed(
        "https://tala.sapumu.com/doc.pdf",
        allowed_domains=["tala.sapumu.com", "app-sapumu.sfo2.digitaloceanspaces.com"],
        document_extensions=["pdf"],
    )
    assert ok

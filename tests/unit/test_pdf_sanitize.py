# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Tests for PDF extractor sanitization.

Background: pypdf sometimes returns raw byte sequences (NUL + low control
chars) when it can't decode a PDF's font-encoding table. Postgres TEXT
columns refuse NUL bytes, so the unsanitized output crashed bulk_insert mid-
run. These tests pin the cleanup rules so the regression can't come back.
"""
from __future__ import annotations

from open_data_jalisco.adapters.extraction.pdf import _is_garbage, _sanitize


def test_sanitize_strips_nul_bytes():
    assert _sanitize("hola\x00mundo") == "holamundo"


def test_sanitize_strips_other_c0_control_chars():
    raw = "ANEXO\n\x01\x02\x03\x04\x05\x06DECRETO\x0b\x0c"
    assert _sanitize(raw) == "ANEXO\nDECRETO"


def test_sanitize_preserves_tab_lf_cr():
    text = "linea1\nlinea2\rcr\ttab"
    assert _sanitize(text) == text


def test_sanitize_preserves_accented_spanish():
    text = "Información Pública — Tala, Jalisco"
    assert _sanitize(text) == text


def test_sanitize_empty_string_is_safe():
    assert _sanitize("") == ""


def test_is_garbage_true_when_mostly_control_chars():
    # Real-world example from Periódico Oficial extraction crash.
    raw = "\x01\x02\x03\x04\x05\x06\x07\x08\x06\t\x07\x08\n\x03\x0b\x0c\x0b\r\x02"
    assert _is_garbage(raw) is True


def test_is_garbage_false_for_real_spanish_text():
    text = "GOBERNADOR CONSTITUCIONAL DEL ESTADO DE JALISCO. Información pública."
    assert _is_garbage(text) is False


def test_is_garbage_false_for_text_with_a_few_control_chars():
    # 5% control chars: the page probably extracted fine with a couple of glyph errors.
    text = "Contenido normal del documento " * 20 + "\x01\x02\x03"
    assert _is_garbage(text) is False


def test_is_garbage_false_for_empty():
    """Empty isn't garbage — it's handled by the needs_ocr path upstream."""
    assert _is_garbage("") is False

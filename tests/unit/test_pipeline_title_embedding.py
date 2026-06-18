# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Verify that the document title is prepended to embedder input.

This is the change that lets a user search "contrato sapumu" and find a
document whose body never mentions "sapumu" but whose title does. We
assert two properties:

1. The text passed to ``EmbeddingProvider.embed`` includes the title.
2. The text persisted into ``Chunk.text`` does NOT include the title — the
   UI keeps showing the raw fragment.
"""
from __future__ import annotations

from open_data_jalisco.ports.chunker import ChunkCandidate
from open_data_jalisco.processing.pipeline import _compose_embedding_input

from ._api_helpers import make_document


def test_title_and_section_are_prepended_to_embedder_input():
    doc = make_document(title="Contrato SAPUMU 2025 prestación de servicios")
    candidate = ChunkCandidate(
        chunk_index=0,
        text="...el monto autorizado asciende a $123,456.00...",
        section_title="CLÁUSULA TERCERA — DEL PRECIO",
    )
    composed = _compose_embedding_input(doc, candidate)

    assert composed.startswith("Contrato SAPUMU 2025 prestación de servicios")
    assert "CLÁUSULA TERCERA — DEL PRECIO" in composed
    assert "...el monto autorizado asciende a $123,456.00..." in composed


def test_composer_handles_missing_section_title():
    doc = make_document(title="Adjudicación directa 001/2025")
    candidate = ChunkCandidate(chunk_index=0, text="cuerpo del documento")
    composed = _compose_embedding_input(doc, candidate)

    assert composed.startswith("Adjudicación directa 001/2025")
    assert composed.endswith("cuerpo del documento")


def test_chunk_text_is_not_mutated_by_composing():
    doc = make_document(title="Documento X")
    candidate = ChunkCandidate(chunk_index=0, text="fragmento original")
    _compose_embedding_input(doc, candidate)

    assert candidate.text == "fragmento original"

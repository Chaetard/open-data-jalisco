# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from open_data_jalisco.ports.text_extractor import ExtractedDocument, ExtractedPage
from open_data_jalisco.processing.chunker import StructureAwareChunker


def _doc_with_pages(pages: list[str]) -> ExtractedDocument:
    return ExtractedDocument(
        full_text="\n\n".join(pages),
        pages=[ExtractedPage(page_number=i + 1, text=t) for i, t in enumerate(pages)],
    )


def test_paginated_emits_chunks_per_page_for_long_pages():
    pages = ["A" * 1000, "B" * 1000, "C" * 1000]
    chunker = StructureAwareChunker(max_chars=900, overlap=100, min_chars=200)
    chunks = chunker.chunk(_doc_with_pages(pages))
    assert len(chunks) >= 3
    for c in chunks:
        assert c.page_start is not None
        assert c.page_end is not None
        assert c.page_start <= c.page_end


def test_paginated_merges_small_pages():
    pages = ["short page 1", "short page 2", "short page 3"]
    chunker = StructureAwareChunker(max_chars=1000, overlap=50, min_chars=200)
    chunks = chunker.chunk(_doc_with_pages(pages))
    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 3


def test_detects_section_title_from_spanish_heading():
    text = "Artículo 12.- Las obligaciones del ayuntamiento incluyen lo siguiente.\n\n" + "x" * 200
    chunker = StructureAwareChunker(max_chars=1000, overlap=50, min_chars=10)
    chunks = chunker.chunk(_doc_with_pages([text]))
    assert chunks
    assert chunks[0].section_title is not None
    assert "Artículo" in chunks[0].section_title or "ARTÍCULO" in chunks[0].section_title.upper()


def test_fallback_paragraph_chunking_for_no_pages():
    body = "\n\n".join([f"Párrafo {i} con contenido relevante." for i in range(30)])
    extracted = ExtractedDocument(full_text=body, pages=[])
    chunker = StructureAwareChunker(max_chars=200, overlap=40, min_chars=50)
    chunks = chunker.chunk(extracted)
    assert len(chunks) > 1
    for i, c in enumerate(chunks):
        assert c.chunk_index == i
        assert len(c.text) <= 250  # max + small slack from paragraph join


def test_chunk_indices_are_sequential():
    pages = ["X" * 600 for _ in range(4)]
    chunker = StructureAwareChunker(max_chars=500, overlap=50, min_chars=100)
    chunks = chunker.chunk(_doc_with_pages(pages))
    for i, c in enumerate(chunks):
        assert c.chunk_index == i


def test_empty_document_returns_no_chunks():
    chunker = StructureAwareChunker()
    assert chunker.chunk(ExtractedDocument(full_text="", pages=[])) == []

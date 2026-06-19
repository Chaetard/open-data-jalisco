# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Semantic-search orchestration shared by the HTTP router and the agent.

Lives outside the API layer so both the ``/search`` endpoint and the answering
agent can call it without importing each other (which would be a cycle: the
router depends on deps, deps builds the agent, the agent searches).
"""
from __future__ import annotations

import time
from uuid import UUID

from .api.schemas import (
    SearchHit,
    SearchResponse,
    chunk_to_out,
    document_to_out,
)
from .domain.chunk import Chunk
from .domain.document import Document
from .domain.jurisdiction import FEDERAL, STATE, infer_jurisdiction
from .ports.embedding_provider import EmbeddingProvider
from .ports.repositories import ChunkRepository, DocumentRepository
from .ports.reranker import Reranker
from .shared.config import get_settings
from .shared.logging import get_logger

logger = get_logger(__name__)

_REFERENCE_LEVELS = (STATE, FEDERAL)


def _rerank_passage(doc: Document, chunk: Chunk) -> str:
    """Text shown to the cross-encoder: title gives it the jurisdiction signal."""
    title = (doc.title or "").strip()
    return f"{title}\n{chunk.text}" if title else chunk.text


def run_semantic_search(
    *,
    q: str,
    limit: int,
    municipality: str | None,
    document_type: str | None,
    source_id: UUID | None,
    local_only: bool,
    chunk_repo: ChunkRepository,
    doc_repo: DocumentRepository,
    embedder: EmbeddingProvider,
    reranker: Reranker | None,
) -> SearchResponse:
    start = time.perf_counter()
    vector = embedder.embed_query(q)

    # Only over-fetch when a post-step needs the extra candidates; otherwise the
    # cheap path is byte-for-byte what it was before reranking existed.
    needs_pool = reranker is not None or local_only
    pool = max(limit, get_settings().rerank_pool) if needs_pool else limit
    matches = chunk_repo.semantic_search(
        vector,
        limit=pool,
        municipality=municipality,
        document_type=document_type,
        source_id=source_id,
    )

    # Resolve each chunk's document. ponytail: N+1 get_by_id over the pool (<=50);
    # batch-fetch by id set if the pool ever grows past a few dozen.
    enriched: list[tuple[Chunk, Document, float]] = []
    for chunk, distance in matches:
        doc = doc_repo.get_by_id(chunk.document_id)
        if doc is None:
            continue
        if local_only and infer_jurisdiction(doc.title) in _REFERENCE_LEVELS:
            continue
        enriched.append((chunk, doc, distance))

    rerank_scores: list[float] | None = None
    reranker_name: str | None = None
    if reranker is not None and enriched:
        passages = [_rerank_passage(doc, chunk) for chunk, doc, _ in enriched]
        scores = reranker.rerank(q, passages)
        order = sorted(range(len(enriched)), key=lambda i: scores[i], reverse=True)
        enriched = [enriched[i] for i in order]
        rerank_scores = [scores[i] for i in order]
        reranker_name = reranker.model

    hits: list[SearchHit] = []
    for idx, (chunk, doc, distance) in enumerate(enriched[:limit]):
        hits.append(
            SearchHit(
                score=max(0.0, 1.0 - float(distance)),
                rerank_score=rerank_scores[idx] if rerank_scores is not None else None,
                chunk=chunk_to_out(chunk),
                document=document_to_out(doc),
            )
        )

    logger.info(
        "search: q=%r local_only=%s pool=%d candidates=%d -> %d hits in %.0fms (rerank=%s)",
        q[:120],
        local_only,
        pool,
        len(enriched),
        len(hits),
        (time.perf_counter() - start) * 1000,
        reranker_name,
    )
    return SearchResponse(
        query=q,
        embedding_provider=embedder.name,
        embedding_model=embedder.model,
        embedding_dimension=embedder.dimension,
        reranker=reranker_name,
        hits=hits,
    )

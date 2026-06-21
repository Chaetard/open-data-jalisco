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
_RRF_K = 60  # standard Reciprocal Rank Fusion constant; dampens low ranks.


def _fuse(
    vector_matches: list[tuple[Chunk, float]],
    lexical_matches: list[tuple[Chunk, float]],
    *,
    limit: int,
) -> list[tuple[Chunk, float | None]]:
    """Reciprocal Rank Fusion of the vector and lexical arms, keyed by chunk id.

    RRF blends two lists using only each item's *rank*, not its score — which is
    exactly why a vector distance and a ts_rank (different scales, opposite
    directions) can be merged without normalising either. Keeps the vector
    distance (for the informational hit score) when the chunk had one.
    """
    rrf: dict[UUID, float] = {}
    chunks: dict[UUID, Chunk] = {}
    distances: dict[UUID, float] = {}
    for rank, (chunk, dist) in enumerate(vector_matches):
        rrf[chunk.id] = rrf.get(chunk.id, 0.0) + 1.0 / (_RRF_K + rank)
        chunks[chunk.id] = chunk
        distances[chunk.id] = dist
    for rank, (chunk, _score) in enumerate(lexical_matches):
        rrf[chunk.id] = rrf.get(chunk.id, 0.0) + 1.0 / (_RRF_K + rank)
        chunks.setdefault(chunk.id, chunk)
    ordered = sorted(rrf, key=lambda cid: rrf[cid], reverse=True)[:limit]
    return [(chunks[cid], distances.get(cid)) for cid in ordered]


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
    year: int | None = None,
    local_markers: frozenset[str] = frozenset(),
) -> SearchResponse:
    start = time.perf_counter()
    # Stage markers logged BEFORE each potentially-slow step (embed model, DB
    # query, rerank model). If one hangs, the log stops at that line and names
    # the culprit; logging only the final summary would show nothing.
    logger.info("search: start q=%r local_only=%s", q[:120], local_only)
    vector = embedder.embed_query(q)

    # Hybrid recall: vector (meaning) + lexical full-text (exact codes, names,
    # amounts the embedder fragments into subwords). Always over-fetch a pool so
    # both arms have candidates to fuse; the reranker — or RRF when there's none
    # — decides the final order.
    pool = max(limit, get_settings().rerank_pool)
    logger.info("search: db query (pool=%d, hybrid)", pool)
    vector_matches = chunk_repo.semantic_search(
        vector,
        limit=pool,
        municipality=municipality,
        document_type=document_type,
        source_id=source_id,
        year=year,
    )
    lexical_matches = chunk_repo.lexical_search(
        q,
        limit=pool,
        municipality=municipality,
        document_type=document_type,
        source_id=source_id,
        year=year,
    )
    matches = _fuse(vector_matches, lexical_matches, limit=pool)
    logger.info(
        "search: vector=%d lexical=%d -> fused=%d",
        len(vector_matches),
        len(lexical_matches),
        len(matches),
    )

    # Resolve each chunk's document. ponytail: N+1 get_by_id over the pool (<=50);
    # batch-fetch by id set if the pool ever grows past a few dozen.
    enriched: list[tuple[Chunk, Document, float | None]] = []
    for chunk, distance in matches:
        doc = doc_repo.get_by_id(chunk.document_id)
        if doc is None:
            continue
        if local_only and infer_jurisdiction(doc.title, local_markers) in _REFERENCE_LEVELS:
            continue
        enriched.append((chunk, doc, distance))

    rerank_scores: list[float] | None = None
    reranker_name: str | None = None
    if reranker is not None and enriched:
        logger.info("search: reranking %d candidates", len(enriched))
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
                # Lexical-only candidates have no vector distance; their real
                # ranking comes from the reranker (or RRF). 0.0 is a placeholder.
                score=max(0.0, 1.0 - distance) if distance is not None else 0.0,
                rerank_score=rerank_scores[idx] if rerank_scores is not None else None,
                chunk=chunk_to_out(chunk),
                document=document_to_out(doc, local_markers),
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

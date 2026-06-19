# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ...domain.chunk import Chunk
from ...domain.document import Document
from ...domain.jurisdiction import FEDERAL, STATE, infer_jurisdiction
from ...ports.embedding_provider import EmbeddingProvider
from ...ports.repositories import ChunkRepository, DocumentRepository
from ...ports.reranker import Reranker
from ...shared.config import get_settings
from ..deps import (
    get_chunk_repository,
    get_document_repository,
    get_embedding_provider,
    get_reranker,
)
from ..schemas import (
    SearchHit,
    SearchRequest,
    SearchResponse,
    chunk_to_out,
    document_to_out,
)

router = APIRouter()
semantic_router = APIRouter()

_REFERENCE_LEVELS = (STATE, FEDERAL)


def _rerank_passage(doc: Document, chunk: Chunk) -> str:
    """Text shown to the cross-encoder: title gives it the jurisdiction signal."""
    title = (doc.title or "").strip()
    return f"{title}\n{chunk.text}" if title else chunk.text


def _run_semantic_search(
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

    return SearchResponse(
        query=q,
        embedding_provider=embedder.name,
        embedding_model=embedder.model,
        embedding_dimension=embedder.dimension,
        reranker=reranker_name,
        hits=hits,
    )


@router.get("", response_model=SearchResponse)
def search_get(
    q: str = Query(min_length=2, description="Free-text query"),
    limit: int = Query(default=10, ge=1, le=50),
    municipality: str | None = None,
    document_type: str | None = None,
    source_id: UUID | None = None,
    local_only: bool = Query(
        default=False, description="Hide republished state/federal reference material"
    ),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
    reranker: Reranker | None = Depends(get_reranker),
) -> SearchResponse:
    """Legacy GET endpoint kept for compatibility. Prefer ``POST /search``."""
    return _run_semantic_search(
        q=q,
        limit=limit,
        municipality=municipality,
        document_type=document_type,
        source_id=source_id,
        local_only=local_only,
        chunk_repo=chunk_repo,
        doc_repo=doc_repo,
        embedder=embedder,
        reranker=reranker,
    )


@router.post("", response_model=SearchResponse)
def search_post(
    body: SearchRequest,
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
    reranker: Reranker | None = Depends(get_reranker),
) -> SearchResponse:
    """Primary search endpoint. Accepts a JSON body with query and filters."""
    return _run_semantic_search(
        q=body.q,
        limit=body.limit,
        municipality=body.municipality,
        document_type=body.document_type,
        source_id=body.source_id,
        local_only=body.local_only,
        chunk_repo=chunk_repo,
        doc_repo=doc_repo,
        embedder=embedder,
        reranker=reranker,
    )


@semantic_router.post("", response_model=SearchResponse)
def semantic_search_post(
    body: SearchRequest,
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
    reranker: Reranker | None = Depends(get_reranker),
) -> SearchResponse:
    """Explicit semantic-search route. Currently equivalent to ``POST /search``."""
    return _run_semantic_search(
        q=body.q,
        limit=body.limit,
        municipality=body.municipality,
        document_type=body.document_type,
        source_id=body.source_id,
        local_only=body.local_only,
        chunk_repo=chunk_repo,
        doc_repo=doc_repo,
        embedder=embedder,
        reranker=reranker,
    )

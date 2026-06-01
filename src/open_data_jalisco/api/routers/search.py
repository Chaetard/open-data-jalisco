# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ...ports.embedding_provider import EmbeddingProvider
from ...ports.repositories import ChunkRepository, DocumentRepository
from ..deps import get_chunk_repository, get_document_repository, get_embedding_provider
from ..schemas import (
    SearchHit,
    SearchRequest,
    SearchResponse,
    chunk_to_out,
    document_to_out,
)

router = APIRouter()
semantic_router = APIRouter()


def _run_semantic_search(
    *,
    q: str,
    limit: int,
    municipality: str | None,
    document_type: str | None,
    source_id: UUID | None,
    chunk_repo: ChunkRepository,
    doc_repo: DocumentRepository,
    embedder: EmbeddingProvider,
) -> SearchResponse:
    [vector] = embedder.embed([q])
    matches = chunk_repo.semantic_search(
        vector,
        limit=limit,
        municipality=municipality,
        document_type=document_type,
        source_id=source_id,
    )

    hits: list[SearchHit] = []
    for chunk, distance in matches:
        doc = doc_repo.get_by_id(chunk.document_id)
        if doc is None:
            continue
        score = max(0.0, 1.0 - float(distance))
        hits.append(
            SearchHit(
                score=score,
                chunk=chunk_to_out(chunk),
                document=document_to_out(doc),
            )
        )

    return SearchResponse(
        query=q,
        embedding_provider=embedder.name,
        embedding_model=embedder.model,
        embedding_dimension=embedder.dimension,
        hits=hits,
    )


@router.get("", response_model=SearchResponse)
def search_get(
    q: str = Query(min_length=2, description="Free-text query"),
    limit: int = Query(default=10, ge=1, le=50),
    municipality: str | None = None,
    document_type: str | None = None,
    source_id: UUID | None = None,
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
) -> SearchResponse:
    """Legacy GET endpoint kept for compatibility. Prefer ``POST /search``."""
    return _run_semantic_search(
        q=q,
        limit=limit,
        municipality=municipality,
        document_type=document_type,
        source_id=source_id,
        chunk_repo=chunk_repo,
        doc_repo=doc_repo,
        embedder=embedder,
    )


@router.post("", response_model=SearchResponse)
def search_post(
    body: SearchRequest,
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
) -> SearchResponse:
    """Primary search endpoint. Accepts a JSON body with query and filters."""
    return _run_semantic_search(
        q=body.q,
        limit=body.limit,
        municipality=body.municipality,
        document_type=body.document_type,
        source_id=body.source_id,
        chunk_repo=chunk_repo,
        doc_repo=doc_repo,
        embedder=embedder,
    )


@semantic_router.post("", response_model=SearchResponse)
def semantic_search_post(
    body: SearchRequest,
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
) -> SearchResponse:
    """Explicit semantic-search route. Currently equivalent to ``POST /search``."""
    return _run_semantic_search(
        q=body.q,
        limit=body.limit,
        municipality=body.municipality,
        document_type=body.document_type,
        source_id=body.source_id,
        chunk_repo=chunk_repo,
        doc_repo=doc_repo,
        embedder=embedder,
    )

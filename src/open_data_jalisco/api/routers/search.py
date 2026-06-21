# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from ...ports.embedding_provider import EmbeddingProvider
from ...ports.repositories import ChunkRepository, DocumentRepository
from ...ports.reranker import Reranker
from ...search_service import run_semantic_search
from ..deps import (
    get_chunk_repository,
    get_document_repository,
    get_embedding_provider,
    get_local_markers,
    get_reranker,
)
from ..schemas import SearchRequest, SearchResponse

router = APIRouter()
semantic_router = APIRouter()


@router.get("", response_model=SearchResponse)
def search_get(
    q: str = Query(min_length=2, description="Free-text query"),
    limit: int = Query(default=10, ge=1, le=50),
    municipality: str | None = None,
    document_type: str | None = None,
    source_id: UUID | None = None,
    year: int | None = Query(default=None, ge=1900, le=2100),
    local_only: bool = Query(
        default=True,
        description="Hide republished state/federal reference material (default on)",
    ),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
    reranker: Reranker | None = Depends(get_reranker),
    local_markers: frozenset[str] = Depends(get_local_markers),
) -> SearchResponse:
    """Legacy GET endpoint kept for compatibility. Prefer ``POST /search``."""
    return run_semantic_search(
        q=q,
        limit=limit,
        municipality=municipality,
        document_type=document_type,
        source_id=source_id,
        year=year,
        local_only=local_only,
        chunk_repo=chunk_repo,
        doc_repo=doc_repo,
        embedder=embedder,
        reranker=reranker,
        local_markers=local_markers,
    )


@router.post("", response_model=SearchResponse)
def search_post(
    body: SearchRequest,
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
    reranker: Reranker | None = Depends(get_reranker),
    local_markers: frozenset[str] = Depends(get_local_markers),
) -> SearchResponse:
    """Primary search endpoint. Accepts a JSON body with query and filters."""
    return run_semantic_search(
        q=body.q,
        limit=body.limit,
        municipality=body.municipality,
        document_type=body.document_type,
        source_id=body.source_id,
        year=body.year,
        local_only=body.local_only,
        chunk_repo=chunk_repo,
        doc_repo=doc_repo,
        embedder=embedder,
        reranker=reranker,
        local_markers=local_markers,
    )


@semantic_router.post("", response_model=SearchResponse)
def semantic_search_post(
    body: SearchRequest,
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    doc_repo: DocumentRepository = Depends(get_document_repository),
    embedder: EmbeddingProvider = Depends(get_embedding_provider),
    reranker: Reranker | None = Depends(get_reranker),
    local_markers: frozenset[str] = Depends(get_local_markers),
) -> SearchResponse:
    """Explicit semantic-search route. Currently equivalent to ``POST /search``."""
    return run_semantic_search(
        q=body.q,
        limit=body.limit,
        municipality=body.municipality,
        document_type=body.document_type,
        source_id=body.source_id,
        year=body.year,
        local_only=body.local_only,
        chunk_repo=chunk_repo,
        doc_repo=doc_repo,
        embedder=embedder,
        reranker=reranker,
        local_markers=local_markers,
    )

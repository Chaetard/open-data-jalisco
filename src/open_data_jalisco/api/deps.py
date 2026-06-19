# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from functools import lru_cache
from pathlib import Path

from ..adapters.embeddings import build_embedding_provider
from ..adapters.llm import build_llm_client
from ..adapters.persistence import (
    PostgresChunkRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
    get_session_factory,
)
from ..adapters.reranking import build_reranker
from ..adapters.storage.local_filesystem import LocalFilesystemRawStorage
from ..agent import AskAgent
from ..ports.embedding_provider import EmbeddingProvider
from ..ports.llm import LLMClient
from ..ports.raw_storage import RawStorage
from ..ports.repositories import ChunkRepository, DocumentRepository, SourceRepository
from ..ports.reranker import Reranker
from ..search_service import run_semantic_search
from ..shared.config import get_settings
from .schemas import SearchHit


@lru_cache
def get_source_repository() -> SourceRepository:
    return PostgresSourceRepository(get_session_factory())


@lru_cache
def get_document_repository() -> DocumentRepository:
    return PostgresDocumentRepository(get_session_factory())


@lru_cache
def get_chunk_repository() -> ChunkRepository:
    return PostgresChunkRepository(get_session_factory())


@lru_cache
def get_raw_storage() -> RawStorage:
    return LocalFilesystemRawStorage(get_settings().raw_storage_path)


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return build_embedding_provider()


@lru_cache
def get_reranker() -> Reranker | None:
    return build_reranker()


@lru_cache
def get_manifests_dir() -> Path:
    return get_settings().manifests_dir


@lru_cache
def get_llm_client() -> LLMClient | None:
    return build_llm_client()


@lru_cache
def get_ask_agent() -> AskAgent | None:
    llm = get_llm_client()
    if llm is None:
        return None
    chunk_repo = get_chunk_repository()
    doc_repo = get_document_repository()
    embedder = get_embedding_provider()
    reranker = get_reranker()

    def search(query: str, local_only: bool, limit: int) -> list[SearchHit]:
        return run_semantic_search(
            q=query,
            limit=limit,
            municipality=None,
            document_type=None,
            source_id=None,
            local_only=local_only,
            chunk_repo=chunk_repo,
            doc_repo=doc_repo,
            embedder=embedder,
            reranker=reranker,
        ).hits

    return AskAgent(llm=llm, search=search, max_iters=get_settings().llm_max_iters)

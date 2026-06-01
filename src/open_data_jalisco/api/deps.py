# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from functools import lru_cache
from pathlib import Path

from ..adapters.embeddings import build_embedding_provider
from ..adapters.persistence import (
    PostgresChunkRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
    get_session_factory,
)
from ..adapters.storage.local_filesystem import LocalFilesystemRawStorage
from ..ports.embedding_provider import EmbeddingProvider
from ..ports.raw_storage import RawStorage
from ..ports.repositories import ChunkRepository, DocumentRepository, SourceRepository
from ..shared.config import get_settings


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
def get_manifests_dir() -> Path:
    return get_settings().manifests_dir

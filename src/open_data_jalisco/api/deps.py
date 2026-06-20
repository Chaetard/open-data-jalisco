# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

import time
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select

from ..adapters.embeddings import build_embedding_provider
from ..adapters.llm import build_llm_client, build_router_client
from ..adapters.persistence import (
    PostgresChunkRepository,
    PostgresDocumentRepository,
    PostgresSourceRepository,
    get_session_factory,
)
from ..adapters.persistence.models import DocumentORM
from ..adapters.reranking import build_reranker
from ..adapters.storage.local_filesystem import LocalFilesystemRawStorage
from ..agent import AskAgent, Router
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


# Corpus shape changes slowly (only during ingestion), so a short TTL cache keeps
# the agent's prompt fresh without a DB hit on every /ask. ponytail: module-level
# cache, fine for a single process; move to Redis only if multi-process drift bites.
_OVERVIEW_TTL_SECONDS = 300
# (timestamp, overview string, municipality-name stopword tokens). One DB read
# feeds both the prompt panorama and the agent's citation stopwords.
_corpus_cache: tuple[float, str, frozenset[str]] | None = None


def _corpus() -> tuple[str, frozenset[str]]:
    global _corpus_cache
    now = time.monotonic()
    if _corpus_cache is not None and now - _corpus_cache[0] < _OVERVIEW_TTL_SECONDS:
        return _corpus_cache[1], _corpus_cache[2]
    overview, munis = _build_corpus()
    _corpus_cache = (now, overview, munis)
    return overview, munis


def corpus_overview() -> str:
    """Compact, cached description of the indexed corpus for the agent prompt."""
    return _corpus()[0]


def corpus_municipalities() -> frozenset[str]:
    """Normalized municipality-name tokens, for citation stopwords (see AskAgent)."""
    return _corpus()[1]


def _build_corpus() -> tuple[str, frozenset[str]]:
    current = DocumentORM.is_current.is_(True)
    with get_session_factory()() as session:
        muni_rows = session.execute(
            select(DocumentORM.municipality, func.count())
            .where(current)
            .group_by(DocumentORM.municipality)
            .order_by(func.count().desc())
        ).all()
        type_rows = session.execute(
            select(DocumentORM.document_type, func.count())
            .where(current)
            .group_by(DocumentORM.document_type)
            .order_by(func.count().desc())
        ).all()
        year_lo, year_hi = session.execute(
            select(func.min(DocumentORM.year), func.max(DocumentORM.year))
            .where(current, DocumentORM.year.isnot(None))
        ).one()
    if not muni_rows:
        return "", frozenset()
    # Each municipality name split into lowercased word tokens ("San Pedro
    # Tlaquepaque" -> san, pedro, tlaquepaque) so they're dropped from title-token
    # citation matching.
    muni_tokens = frozenset(
        tok for m, _ in muni_rows for tok in str(m).lower().split()
    )
    munis = ", ".join(f"{m} ({n})" for m, n in muni_rows[:20])
    types = ", ".join(f"{t} ({n})" for t, n in type_rows)
    years = f"{year_lo}–{year_hi}" if year_lo and year_hi else "sin fechar"
    overview = (
        "PANORAMA DEL CORPUS (datos disponibles AHORA; úsalo para acotar tus "
        "búsquedas con los parámetros municipality/year y no asumir cobertura):\n"
        f"- Municipios (docs): {munis}\n"
        f"- Años: {years}\n"
        f"- Tipos de documento (docs): {types}\n"
        "Si te piden un municipio o año que NO aparezca aquí, dilo claramente "
        "(no hay documentos de esa cobertura) en vez de inventar."
    )
    return overview, muni_tokens


@lru_cache
def get_ask_agent() -> AskAgent | None:
    llm = get_llm_client()
    if llm is None:
        return None
    chunk_repo = get_chunk_repository()
    doc_repo = get_document_repository()
    embedder = get_embedding_provider()
    reranker = get_reranker()

    def search(
        *,
        query: str,
        local_only: bool,
        limit: int,
        municipality: str | None = None,
        year: int | None = None,
    ) -> list[SearchHit]:
        return run_semantic_search(
            q=query,
            limit=limit,
            municipality=municipality,
            document_type=None,
            source_id=None,
            local_only=local_only,
            chunk_repo=chunk_repo,
            doc_repo=doc_repo,
            embedder=embedder,
            reranker=reranker,
            year=year,
        ).hits

    router_client = build_router_client()
    router = Router(router_client) if router_client is not None else None

    return AskAgent(
        llm=llm,
        search=search,
        max_iters=get_settings().llm_max_iters,
        corpus_overview=corpus_overview,
        corpus_municipalities=corpus_municipalities,
        router=router,
    )

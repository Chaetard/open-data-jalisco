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
from ..shared.logging import get_logger
from .schemas import SearchHit

logger = get_logger(__name__)


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
# (timestamp, overview string, citation-stopword tokens, jurisdiction markers).
# One DB read feeds the prompt panorama, the agent's citation stopwords, and the
# search's jurisdiction inference.
_corpus_cache: tuple[float, str, frozenset[str], frozenset[str]] | None = None


def _corpus() -> tuple[str, frozenset[str], frozenset[str]]:
    global _corpus_cache
    now = time.monotonic()
    if _corpus_cache is not None and now - _corpus_cache[0] < _OVERVIEW_TTL_SECONDS:
        return _corpus_cache[1], _corpus_cache[2], _corpus_cache[3]
    overview, munis, markers = _build_corpus()
    _corpus_cache = (now, overview, munis, markers)
    return overview, munis, markers


def corpus_overview() -> str:
    """Compact, cached description of the indexed corpus for the agent prompt."""
    return _corpus()[0]


def corpus_municipalities() -> frozenset[str]:
    """Normalized municipality-name tokens, for citation stopwords (see AskAgent)."""
    return _corpus()[1]


def corpus_local_markers() -> frozenset[str]:
    """Full municipality names (lowercased) used as jurisdiction local-markers.

    Lets ``infer_jurisdiction`` recognise every ingested municipality as local
    instead of hardcoding the pilot names — so ``local_only`` stops hiding, say,
    a "Egresos Tequila Jalisco 2024" as if it were state material.
    """
    return _corpus()[2]


def get_local_markers() -> frozenset[str]:
    """Best-effort wrapper for the search routers' jurisdiction markers.

    A DB hiccup (or no DB at all, e.g. unit tests that don't override this)
    degrades to structural-only jurisdiction instead of failing the search.
    """
    try:
        return corpus_local_markers()
    except Exception:
        logger.warning("deps: corpus local markers unavailable", exc_info=True)
        return frozenset()


def _build_corpus() -> tuple[str, frozenset[str], frozenset[str]]:
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
        return "", frozenset(), frozenset()
    # Each municipality name split into lowercased word tokens ("San Pedro
    # Tlaquepaque" -> san, pedro, tlaquepaque) so they're dropped from title-token
    # citation matching.
    muni_tokens = frozenset(
        tok for m, _ in muni_rows for tok in str(m).lower().split()
    )
    # Full names (not split) for jurisdiction inference: "San Pedro Tlaquepaque"
    # must match as a whole, never as the bare token "san".
    local_markers = frozenset(str(m).lower() for m, _ in muni_rows)
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
    return overview, muni_tokens, local_markers


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
        document_type: str | None = None,
    ) -> list[SearchHit]:
        return run_semantic_search(
            q=query,
            limit=limit,
            municipality=municipality,
            document_type=document_type,
            source_id=None,
            local_only=local_only,
            chunk_repo=chunk_repo,
            doc_repo=doc_repo,
            embedder=embedder,
            reranker=reranker,
            year=year,
            local_markers=get_local_markers(),
        ).hits

    def read_document(*, url: str, page: int | None = None) -> list[dict[str, object]]:
        doc = doc_repo.find_current_by_official_url(url)
        if doc is None:
            return []
        chunks = chunk_repo.list_by_document(doc.id)  # ordered by chunk_index
        if page is not None:
            # Chunks whose page range touches [page-1, page+1] — the hit's page in
            # context. Fall back to the document start if the page matched nothing.
            window = [
                c
                for c in chunks
                if c.page_start is not None
                and c.page_start <= page + 1
                and (c.page_end or c.page_start) >= page - 1
            ]
            chunks = window or chunks
        return [
            {"page_start": c.page_start, "page_end": c.page_end, "text": c.text}
            for c in chunks[:10]
        ]

    def coverage(
        *,
        municipality: str | None = None,
        year: int | None = None,
        document_type: str | None = None,
    ) -> dict[str, object]:
        common = {
            "municipality": municipality,
            "year": year,
            "document_type": document_type,
        }
        return {
            "municipio": municipality,
            "anio": year,
            "tipo": document_type,
            "buscables": doc_repo.count_documents(**common, processing_status="indexed"),
            "escaneados_sin_texto": doc_repo.count_documents(
                **common, processing_status="needs_ocr"
            ),
            "total": doc_repo.count_documents(**common),
        }

    router_client = build_router_client()
    router = (
        Router(router_client, corpus_overview=corpus_overview)
        if router_client is not None
        else None
    )

    return AskAgent(
        llm=llm,
        search=search,
        max_iters=get_settings().llm_max_iters,
        corpus_overview=corpus_overview,
        corpus_municipalities=corpus_municipalities,
        router=router,
        read_document=read_document,
        coverage=coverage,
    )

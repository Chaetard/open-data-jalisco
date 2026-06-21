# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from collections.abc import Callable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ...shared.config import get_settings
from ...shared.logging import get_logger
from .models import Base

logger = get_logger(__name__)

_engine: Engine | None = None
_session_factory: Callable[[], Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            future=True,
            pool_pre_ping=True,
            # Fail fast on a dead/unreachable DB instead of blocking the request
            # (and the user's browser) on a TCP connect that never returns.
            # ponytail: 10s constant; lift to a setting if prod needs tuning.
            connect_args={"connect_timeout": 10},
        )
    return _engine


def get_session_factory() -> Callable[[], Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _session_factory


def init_db() -> None:
    """Create pgvector extension and all tables. Idempotent."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        # GIN index backing the lexical (full-text) search arm. Must match the
        # exact expression used in chunk_repository.lexical_search so the planner
        # uses it. Created after create_all (the chunks table must exist).
        # Accent-insensitive full-text. The Spanish FTS config does NOT fold
        # accents: to_tsvector('spanish','adjudicación') stems to 'adjud' but
        # 'adjudicacion' (no accent) stays whole, so they never match — a citizen
        # typing without accents misses every accented document. An IMMUTABLE
        # unaccent wrapper fixes it; the 2-arg form pins the dictionary, which is
        # what makes it safe to mark IMMUTABLE and therefore usable in an index.
        conn.execute(
            text(
                "CREATE OR REPLACE FUNCTION odj_unaccent(text) RETURNS text "
                "LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT AS "
                "$$ SELECT unaccent('unaccent', $1) $$"
            )
        )
        # Swap the old accent-sensitive GIN for the unaccent-folded one. New name
        # + drop-old keeps init_db idempotent. lexical_search must mirror this
        # exact expression (to_tsvector('spanish', odj_unaccent(text))) or the
        # planner won't use the index.
        conn.execute(text("DROP INDEX IF EXISTS ix_chunks_text_fts"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chunks_text_fts_unaccent "
                "ON chunks USING gin (to_tsvector('spanish', odj_unaccent(text)))"
            )
        )
        # ANN index backing the vector arm. WITHOUT it, semantic_search is a
        # sequential scan that recomputes cosine distance over every chunk —
        # fine at hundreds of rows, O(N) and slow at the 100k+ chunks larger
        # ingests produce. HNSW gives recall-preserving ~O(log N) search; opclass
        # MUST match the query operator (cosine_distance -> <=> -> vector_cosine_ops).
        # m / ef_construction are pgvector's recommended production defaults.
        # ponytail: plain CREATE INDEX locks the table while building; for an
        # already-huge chunks table build it CONCURRENTLY out-of-band instead.
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw "
                "ON chunks USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 200)"
            )
        )
        # Filter column on both search arms; index it so municipality/year
        # filtered searches don't add a scan on top of the index lookup.
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chunks_year ON chunks (year)"))
        # create_all adds columns only to NEW tables; existing DBs need the
        # content-derived title column added explicitly. Idempotent.
        conn.execute(
            text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS inferred_title text")
        )
        # pgvector >= 0.8: with a WHERE filter (municipality/year) an HNSW scan
        # applies the filter AFTER picking its top-k, so a selective filter can
        # return fewer than `limit` rows. iterative_scan keeps scanning until
        # enough survive; relaxed_order trades a little ordering for recall.
        # ef_search widens the candidate pool. Set at the database level so every
        # new connection inherits them without per-query code; namespaced GUCs
        # are accepted as placeholders even on pgvector < 0.8 (then simply unused).
        dbname = conn.execute(text("SELECT current_database()")).scalar_one()
        conn.execute(text(f'ALTER DATABASE "{dbname}" SET hnsw.ef_search = 100'))
        conn.execute(
            text(f"ALTER DATABASE \"{dbname}\" SET hnsw.iterative_scan = 'relaxed_order'")
        )
    logger.info("db.init.done url=%s", _redact(get_settings().database_url))


def _redact(url: str) -> str:
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        userinfo, host = rest.split("@", 1)
        if ":" in userinfo:
            user, _ = userinfo.split(":", 1)
            return f"{scheme}://{user}:***@{host}"
    return url

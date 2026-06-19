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
    Base.metadata.create_all(engine)
    logger.info("db.init.done url=%s", _redact(get_settings().database_url))


def _redact(url: str) -> str:
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        userinfo, host = rest.split("@", 1)
        if ":" in userinfo:
            user, _ = userinfo.split(":", 1)
            return f"{scheme}://{user}:***@{host}"
    return url

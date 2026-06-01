# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.source import Source
from ...shared.time import utcnow
from ._mappers import source_to_domain, source_to_orm
from .models import SourceORM


class PostgresSourceRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._sf = session_factory

    def upsert(self, source: Source) -> Source:
        with self._sf() as session:
            existing = session.scalar(select(SourceORM).where(SourceORM.slug == source.slug))
            if existing is not None:
                existing.name = source.name
                existing.kind = source.kind.value
                existing.municipality = source.municipality
                existing.official_url = source.official_url
                existing.description = source.description
                existing.metadata_json = source.metadata
                existing.is_active = source.is_active
                existing.updated_at = utcnow()
                session.commit()
                session.refresh(existing)
                return source_to_domain(existing)

            orm = source_to_orm(source)
            session.add(orm)
            session.commit()
            session.refresh(orm)
            return source_to_domain(orm)

    def get_by_slug(self, slug: str) -> Source | None:
        with self._sf() as session:
            orm = session.scalar(select(SourceORM).where(SourceORM.slug == slug))
            return source_to_domain(orm) if orm else None

    def get_by_id(self, source_id: UUID) -> Source | None:
        with self._sf() as session:
            orm = session.get(SourceORM, source_id)
            return source_to_domain(orm) if orm else None

    def list_active(self) -> list[Source]:
        with self._sf() as session:
            rows = session.scalars(
                select(SourceORM).where(SourceORM.is_active.is_(True)).order_by(SourceORM.slug)
            ).all()
            return [source_to_domain(r) for r in rows]

    def list_all(self) -> list[Source]:
        with self._sf() as session:
            rows = session.scalars(select(SourceORM).order_by(SourceORM.slug)).all()
            return [source_to_domain(r) for r in rows]

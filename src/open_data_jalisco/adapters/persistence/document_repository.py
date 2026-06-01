from collections.abc import Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.document import Document
from ...shared.time import utcnow
from ._mappers import document_to_domain, document_to_orm
from .models import DocumentORM


class PostgresDocumentRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._sf = session_factory

    def get_by_id(self, document_id: UUID) -> Document | None:
        with self._sf() as session:
            orm = session.get(DocumentORM, document_id)
            return document_to_domain(orm) if orm else None

    def find_by_url_and_hash(
        self, source_id: UUID, official_url: str, sha256: str
    ) -> Document | None:
        with self._sf() as session:
            orm = session.scalar(
                select(DocumentORM).where(
                    DocumentORM.source_id == source_id,
                    DocumentORM.official_url == official_url,
                    DocumentORM.sha256 == sha256,
                )
            )
            return document_to_domain(orm) if orm else None

    def find_current_by_url(self, source_id: UUID, official_url: str) -> Document | None:
        with self._sf() as session:
            orm = session.scalar(
                select(DocumentORM)
                .where(
                    DocumentORM.source_id == source_id,
                    DocumentORM.official_url == official_url,
                    DocumentORM.is_current.is_(True),
                )
                .order_by(DocumentORM.version.desc())
            )
            return document_to_domain(orm) if orm else None

    def insert_new_version(
        self, document: Document, supersedes: Document | None
    ) -> Document:
        with self._sf() as session:
            if supersedes is not None:
                prior = session.get(DocumentORM, supersedes.id)
                if prior is not None:
                    prior.is_current = False
                    prior.superseded_by = document.id
                    prior.updated_at = utcnow()
                    document.version = prior.version + 1

            orm = document_to_orm(document)
            session.add(orm)
            session.commit()
            session.refresh(orm)
            return document_to_domain(orm)

    def update(self, document: Document) -> Document:
        with self._sf() as session:
            orm = session.get(DocumentORM, document.id)
            if orm is None:
                raise LookupError(f"Document not found: {document.id}")
            orm.processing_status = document.processing_status.value
            orm.needs_ocr = document.needs_ocr
            orm.extraction_error = document.extraction_error
            orm.title = document.title
            orm.document_type = document.document_type.value
            orm.year = document.year
            orm.metadata_json = document.metadata
            orm.updated_at = utcnow()
            session.commit()
            session.refresh(orm)
            return document_to_domain(orm)

    def list_documents(
        self,
        *,
        source_id: UUID | None = None,
        municipality: str | None = None,
        document_type: str | None = None,
        year: int | None = None,
        current_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        with self._sf() as session:
            stmt = select(DocumentORM)
            if current_only:
                stmt = stmt.where(DocumentORM.is_current.is_(True))
            if source_id is not None:
                stmt = stmt.where(DocumentORM.source_id == source_id)
            if municipality is not None:
                stmt = stmt.where(DocumentORM.municipality == municipality)
            if document_type is not None:
                stmt = stmt.where(DocumentORM.document_type == document_type)
            if year is not None:
                stmt = stmt.where(DocumentORM.year == year)
            stmt = stmt.order_by(DocumentORM.captured_at.desc()).limit(limit).offset(offset)
            rows = session.scalars(stmt).all()
            return [document_to_domain(r) for r in rows]

    def list_pending(
        self, limit: int = 50, *, include_failed: bool = False
    ) -> list[Document]:
        statuses = ["pending", "failed"] if include_failed else ["pending"]
        with self._sf() as session:
            rows = session.scalars(
                select(DocumentORM)
                .where(
                    DocumentORM.processing_status.in_(statuses),
                    DocumentORM.is_current.is_(True),
                )
                .order_by(DocumentORM.created_at.asc())
                .limit(limit)
            ).all()
            return [document_to_domain(r) for r in rows]

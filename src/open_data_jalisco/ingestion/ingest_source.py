# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from ..domain.document import Document
from ..domain.enums import DocumentType
from ..domain.source import Source
from ..ports.raw_storage import RawStorage
from ..ports.repositories import DocumentRepository, SourceRepository
from ..ports.scraper import ScrapedDocument, ScraperPlanEntry
from ..shared.hashing import sha256_bytes
from ..shared.logging import get_logger
from ..shared.time import utcnow
from ._url_inference import infer_year_month_from_url
from .scraper_factory import build_scraper
from .source_loader import SourceConfig, find_source_config

logger = get_logger(__name__)

_PLACEHOLDER_FRAGMENTS = ("example.invalid", "reemplazar", "<replace>")


@dataclass
class IngestionResult:
    source_slug: str
    dry_run: bool = False
    documents_seen: int = 0
    documents_inserted: int = 0
    documents_versioned: int = 0
    documents_unchanged: int = 0
    documents_failed: int = 0
    documents_skipped: int = 0
    direct_urls: list[str] = field(default_factory=list)
    seed_urls_checked: list[str] = field(default_factory=list)
    content_pages_checked: list[str] = field(default_factory=list)
    discovered_urls: list[str] = field(default_factory=list)
    skipped_urls: list[dict[str, str]] = field(default_factory=list)
    planned_urls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class PlaceholderUrlError(ValueError):
    """Raised when the source config still contains placeholder URLs."""


class IngestSourceUseCase:
    def __init__(
        self,
        *,
        source_repo: SourceRepository,
        document_repo: DocumentRepository,
        raw_storage: RawStorage,
    ):
        self._source_repo = source_repo
        self._doc_repo = document_repo
        self._raw = raw_storage

    def execute(
        self,
        source_slug: str,
        *,
        limit: int = 5,
        dry_run: bool = False,
        timeout: int | None = None,
        user_agent: str | None = None,
    ) -> IngestionResult:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")

        config = find_source_config(source_slug)
        _reject_placeholders(config)

        scraper = build_scraper(
            config.scraper, timeout=timeout, user_agent=user_agent
        )
        scraper_cfg = {**config.scraper, "slug": config.slug}

        # Phase 1 — planning. Fetches seed HTML (cheap) but never the documents
        # themselves. Both dry-run and real-run go through this.
        plan = scraper.plan(scraper_cfg, limit=limit)

        result = IngestionResult(
            source_slug=config.slug,
            dry_run=dry_run,
            direct_urls=list(plan.direct_urls),
            seed_urls_checked=list(plan.seed_urls_checked),
            content_pages_checked=list(plan.content_pages_checked),
            discovered_urls=list(plan.discovered_urls),
            skipped_urls=list(plan.skipped_urls),
            planned_urls=[entry.url for entry in plan.entries],
            documents_skipped=len(plan.skipped_urls),
        )

        if dry_run:
            result.documents_seen = len(plan.entries)
            logger.info(
                "ingest.plan.done slug=%s direct=%d discovered=%d planned=%d skipped=%d",
                config.slug,
                len(plan.direct_urls),
                len(plan.discovered_urls),
                len(plan.entries),
                len(plan.skipped_urls),
            )
            return result

        # Phase 2 — real run: persist source, fetch each planned URL,
        # hash, store raw bytes, insert/version document rows.
        source = self._upsert_source(config)
        for entry in plan.entries:
            result.documents_seen += 1
            try:
                content, mime, ext = scraper.fetch(entry.url)
            except Exception as e:
                logger.error("ingest.fetch_failed url=%s err=%r", entry.url, e)
                result.documents_failed += 1
                result.errors.append(f"{entry.url}: fetch_failed: {e!r}")
                continue

            scraped = ScrapedDocument(
                content=content,
                official_url=entry.url,
                mime_type=mime,
                extension=ext,
                title=entry.title,
                document_type=entry.document_type,
                year=entry.year,
                metadata=entry.metadata or {},
            )
            try:
                self._process_one(source=source, scraped=scraped, result=result)
            except Exception as e:
                logger.exception("ingest.process_failed url=%s", entry.url)
                result.documents_failed += 1
                result.errors.append(f"{entry.url}: {e!r}")

        logger.info(
            "ingest.done slug=%s seen=%d new=%d versioned=%d unchanged=%d failed=%d",
            result.source_slug,
            result.documents_seen,
            result.documents_inserted,
            result.documents_versioned,
            result.documents_unchanged,
            result.documents_failed,
        )
        return result

    def execute_from_entries(
        self,
        source_slug: str,
        entries: Iterable[ScraperPlanEntry],
        *,
        dry_run: bool = False,
        timeout: int | None = None,
        user_agent: str | None = None,
    ) -> IngestionResult:
        """Ingest a pre-built list of ``ScraperPlanEntry`` (e.g. from a candidates file).

        Bypasses the planning phase — entries are assumed to be already
        filtered, validated against allowed_domains/document_extensions, and
        deduplicated by URL. The download + hash + version flow is identical
        to ``execute``: same source upsert, same ``_process_one``, same
        idempotency guarantee (URL + sha256).

        Dry-run NEVER touches the repos/storage and NEVER fetches documents.
        """
        entries = list(entries)
        config = find_source_config(source_slug)
        _reject_placeholders(config)

        result = IngestionResult(
            source_slug=config.slug,
            dry_run=dry_run,
            discovered_urls=[e.url for e in entries],
            planned_urls=[e.url for e in entries],
        )

        if dry_run:
            result.documents_seen = len(entries)
            logger.info(
                "ingest.from_entries.plan slug=%s planned=%d",
                config.slug,
                len(entries),
            )
            return result

        scraper = build_scraper(
            config.scraper, timeout=timeout, user_agent=user_agent
        )
        source = self._upsert_source(config)
        for entry in entries:
            result.documents_seen += 1
            try:
                content, mime, ext = scraper.fetch(entry.url)
            except Exception as e:
                logger.error(
                    "ingest.from_entries.fetch_failed url=%s err=%r", entry.url, e
                )
                result.documents_failed += 1
                result.errors.append(f"{entry.url}: fetch_failed: {e!r}")
                continue

            scraped = ScrapedDocument(
                content=content,
                official_url=entry.url,
                mime_type=mime,
                extension=ext,
                title=entry.title,
                document_type=entry.document_type,
                year=entry.year,
                metadata=entry.metadata or {},
            )
            try:
                self._process_one(source=source, scraped=scraped, result=result)
            except Exception as e:
                logger.exception("ingest.from_entries.process_failed url=%s", entry.url)
                result.documents_failed += 1
                result.errors.append(f"{entry.url}: {e!r}")

        logger.info(
            "ingest.from_entries.done slug=%s seen=%d new=%d versioned=%d "
            "unchanged=%d failed=%d",
            result.source_slug,
            result.documents_seen,
            result.documents_inserted,
            result.documents_versioned,
            result.documents_unchanged,
            result.documents_failed,
        )
        return result

    def _upsert_source(self, config: SourceConfig) -> Source:
        return self._source_repo.upsert(
            Source(
                slug=config.slug,
                name=config.name,
                kind=config.kind,
                municipality=config.municipality,
                official_url=config.official_url,
                description=config.description,
                metadata=config.metadata,
                is_active=config.is_active,
            )
        )

    def _process_one(
        self,
        *,
        source: Source,
        scraped: ScrapedDocument,
        result: IngestionResult,
    ) -> None:
        sha = sha256_bytes(scraped.content)
        current = self._doc_repo.find_current_by_url(source.id, scraped.official_url)
        if current is not None and current.sha256 == sha:
            result.documents_unchanged += 1
            logger.debug("ingest.unchanged url=%s sha256=%s", scraped.official_url, sha)
            return

        captured_at = utcnow()
        storage_path = self._raw.store(
            content=scraped.content,
            sha256=sha,
            source_slug=source.slug,
            captured_at=captured_at,
            extension=scraped.extension,
        )

        year, metadata = _enrich_year_metadata(
            explicit_year=scraped.year,
            url=scraped.official_url,
            base_metadata=scraped.metadata,
        )

        document = Document(
            source_id=source.id,
            sha256=sha,
            official_url=scraped.official_url,
            captured_url=scraped.official_url,
            mime_type=scraped.mime_type,
            storage_path=storage_path,
            file_size=len(scraped.content),
            captured_at=captured_at,
            municipality=source.municipality,
            document_type=_parse_doc_type(scraped.document_type),
            title=scraped.title,
            year=year,
            metadata=metadata,
        )

        if current is None:
            self._doc_repo.insert_new_version(document, supersedes=None)
            result.documents_inserted += 1
        else:
            self._doc_repo.insert_new_version(document, supersedes=current)
            result.documents_versioned += 1


def _reject_placeholders(config: SourceConfig) -> None:
    if _is_placeholder(config.official_url):
        raise PlaceholderUrlError(
            f"Source {config.slug!r} has a placeholder official_url "
            f"({config.official_url!r}). Replace it with a real URL before ingesting."
        )
    scraper_cfg = config.scraper or {}
    direct_entries = (
        scraper_cfg.get("direct_documents")
        or scraper_cfg.get("documents")
        or []
    )
    for entry in direct_entries:
        url = (entry or {}).get("url")
        if url and _is_placeholder(url):
            raise PlaceholderUrlError(
                f"Source {config.slug!r} has a placeholder document URL "
                f"({url!r}). Replace it with a real URL before ingesting."
            )
    for seed in scraper_cfg.get("seed_urls") or []:
        if _is_placeholder(seed):
            raise PlaceholderUrlError(
                f"Source {config.slug!r} has a placeholder seed_url "
                f"({seed!r}). Replace it with a real URL before ingesting."
            )


def _is_placeholder(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.lower()
    return any(fragment in lowered for fragment in _PLACEHOLDER_FRAGMENTS)


def _parse_doc_type(value: str | None) -> DocumentType:
    if not value:
        return DocumentType.UNKNOWN
    try:
        return DocumentType(value)
    except ValueError:
        return DocumentType.OTHER


def _enrich_year_metadata(
    *,
    explicit_year: int | None,
    url: str,
    base_metadata: dict[str, Any] | None,
) -> tuple[int | None, dict[str, Any] | None]:
    """Combine YAML-provided year with URL-inferred year/month.

    - If YAML provided a year, keep it.
    - Otherwise, infer year from URL ``/YYYY/MM/`` segments.
    - Always record an ``inferred_month`` in metadata when the URL exposes one
      and YAML did not already set the same key.
    - Tag the inference with ``year_inferred_from_url=True`` so callers can
      tell explicit values apart from heuristics.
    """
    inferred_year, inferred_month = infer_year_month_from_url(url)
    metadata: dict[str, Any] = dict(base_metadata or {})

    year = explicit_year
    if year is None and inferred_year is not None:
        year = inferred_year
        metadata.setdefault("year_inferred_from_url", True)

    if inferred_month is not None:
        metadata.setdefault("inferred_month", inferred_month)

    return year, (metadata or None)

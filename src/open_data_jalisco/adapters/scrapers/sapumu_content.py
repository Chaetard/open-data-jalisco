# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Scraper for SAPUMU content pages.

A SAPUMU content page (e.g. ``https://<municipio>.sapumu.com/.../contenido/63``)
embeds its document list as JSON in a ``<level-content :content="...">`` tag.
This scraper:
1. Fetches each configured content page once (no recursion).
2. Parses the JSON via ``_sapumu_parser``.
3. Emits an entry per file, validated against ``allowed_domains`` and
   ``document_extensions``.
4. Optionally merges with ``direct_documents`` (deduped by URL).

Expected ``source_config`` shape::

    scraper:
      type: sapumu_content
      content_pages:
        - "https://tala.sapumu.com/.../contenido/63"
        - "https://tala.sapumu.com/.../contenido/53"
      allowed_domains: [...]
      document_extensions: [pdf, xlsx]
      direct_documents:                # optional manual fallback
        - url: "..."
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from ...ports.scraper import ScrapedDocument, ScraperPlan, ScraperPlanEntry
from ...shared.logging import get_logger
from ._sapumu_parser import extract_level_content_json, iter_files_from_content
from ._validation import is_url_allowed
from .base import HttpScraper

logger = get_logger(__name__)


class SapumuContentScraper(HttpScraper):
    def __init__(
        self,
        *,
        user_agent: str | None = None,
        timeout: int | None = None,
        html_fetcher: Callable[[str], str] | None = None,
    ):
        super().__init__(user_agent=user_agent, timeout=timeout)
        # Inject a deterministic fetcher in tests to avoid network.
        self._html_fetcher = html_fetcher

    # ------------------------------------------------------------------
    # planning
    # ------------------------------------------------------------------

    def plan(self, source_config: dict[str, Any], *, limit: int) -> ScraperPlan:
        if limit <= 0:
            raise ValueError("limit must be a positive integer")

        slug = source_config.get("slug")
        allowed_domains = source_config.get("allowed_domains") or []
        document_extensions = source_config.get("document_extensions") or []

        plan = ScraperPlan()
        seen_urls: set[str] = set()
        candidates: list[ScraperPlanEntry] = []

        # 1) direct_documents — manual fallback / overrides (processed first)
        direct_entries = (
            source_config.get("direct_documents")
            or source_config.get("documents")  # legacy alias
            or []
        )
        for entry in direct_entries:
            entry = entry or {}
            url = entry.get("url")
            if not url:
                plan.skipped_urls.append({"url": "", "reason": "missing_url_in_entry"})
                continue
            allowed, reason = is_url_allowed(
                url,
                allowed_domains=allowed_domains,
                document_extensions=document_extensions,
            )
            if not allowed:
                plan.skipped_urls.append({"url": url, "reason": reason})
                logger.warning(
                    "scraper.sapumu.direct_rejected url=%s reason=%s", url, reason
                )
                continue
            if url in seen_urls:
                plan.skipped_urls.append({"url": url, "reason": "duplicate"})
                continue
            seen_urls.add(url)
            plan.direct_urls.append(url)
            candidates.append(
                ScraperPlanEntry(
                    url=url,
                    source="direct",
                    title=entry.get("title"),
                    document_type=entry.get("document_type"),
                    year=entry.get("year"),
                    metadata=entry.get("metadata") or {},
                )
            )

        # 2) content_pages → fetch HTML → parse JSON → walk files
        for page in source_config.get("content_pages") or []:
            plan.content_pages_checked.append(page)
            try:
                html = self._fetch_html(page)
            except Exception as e:
                logger.error(
                    "scraper.sapumu.content_fetch_failed url=%s err=%r", page, e
                )
                plan.skipped_urls.append(
                    {"url": page, "reason": f"content_fetch_failed:{e!r}"}
                )
                continue

            content_data = extract_level_content_json(html)
            if content_data is None:
                logger.warning(
                    "scraper.sapumu.no_level_content url=%s "
                    "(no <level-content :content=...> tag found)",
                    page,
                )
                plan.skipped_urls.append(
                    {"url": page, "reason": "no_level_content_found"}
                )
                continue

            for file_entry in iter_files_from_content(content_data):
                file_url = file_entry.get("full_url")
                if not file_url:
                    plan.skipped_urls.append(
                        {"url": "", "reason": "file_missing_full_url"}
                    )
                    continue
                allowed, reason = is_url_allowed(
                    file_url,
                    allowed_domains=allowed_domains,
                    document_extensions=document_extensions,
                )
                if not allowed:
                    plan.skipped_urls.append({"url": file_url, "reason": reason})
                    continue
                if file_url in seen_urls:
                    plan.skipped_urls.append({"url": file_url, "reason": "duplicate"})
                    continue
                seen_urls.add(file_url)
                plan.discovered_urls.append(file_url)
                candidates.append(_plan_entry_from_sapumu(file_entry, source_page=page))

        plan.entries = candidates[:limit]

        logger.info(
            "scraper.sapumu.plan.done slug=%s direct=%d pages=%d discovered=%d "
            "skipped=%d entries=%d (cap=%d)",
            slug,
            len(plan.direct_urls),
            len(plan.content_pages_checked),
            len(plan.discovered_urls),
            len(plan.skipped_urls),
            len(plan.entries),
            limit,
        )
        return plan

    # ------------------------------------------------------------------
    # fetching
    # ------------------------------------------------------------------

    def scrape(
        self, source_config: dict[str, Any], *, limit: int
    ) -> Iterable[ScrapedDocument]:
        plan = self.plan(source_config, limit=limit)
        for entry in plan.entries:
            try:
                content, mime, ext = self.fetch(entry.url)
            except Exception as e:
                logger.error("scraper.sapumu.fetch_failed url=%s err=%r", entry.url, e)
                continue
            yield ScrapedDocument(
                content=content,
                official_url=entry.url,
                mime_type=mime,
                extension=ext,
                title=entry.title,
                document_type=entry.document_type,
                year=entry.year,
                metadata=entry.metadata or {},
            )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _fetch_html(self, url: str) -> str:
        if self._html_fetcher is not None:
            return self._html_fetcher(url)
        content, _mime, _ext = self.fetch(url)
        return content.decode("utf-8", errors="replace")


def _plan_entry_from_sapumu(file: dict[str, Any], *, source_page: str) -> ScraperPlanEntry:
    """Build a ScraperPlanEntry from a cleaned SAPUMU file dict."""
    return ScraperPlanEntry(
        url=file["full_url"],
        source="discovered",
        title=file.get("title") or file.get("name"),
        document_type=None,
        year=file.get("year"),
        metadata={
            "source_page": source_page,
            "sapumu": {
                "content_id": file.get("content_id"),
                "content_title": file.get("content_title"),
                "file_id": file.get("id"),
                "slug": file.get("slug"),
                "date_at": file.get("date_at"),
                "file_name": file.get("file_name"),
                "mime_type": file.get("mime_type"),
                "size": file.get("size"),
                "extension": file.get("extension"),
                "month": file.get("month"),
                "year": file.get("year"),
            },
        },
    )

# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

from collections.abc import Callable, Iterable
from typing import Any

from ...ports.scraper import ScrapedDocument, ScraperPlan, ScraperPlanEntry
from ...shared.logging import get_logger
from ._discovery import extract_document_links
from ._validation import is_url_allowed
from .base import HttpScraper

logger = get_logger(__name__)


class GenericHttpScraper(HttpScraper):
    """Generic scraper: explicit direct URLs + shallow seed-HTML discovery.

    Expected ``source_config`` shape::

        seed_urls:                          # optional HTML index pages
          - "https://...transparency"
        direct_documents:                   # optional explicit URLs
          - url: "https://...file.pdf"
            title: "..."
            document_type: contract        # optional enum value
            year: 2025
            metadata: {...}
        documents:                          # legacy alias for direct_documents
          - ...
        allowed_domains:                   # optional host allow-list
          - example.com
        document_extensions:               # optional extension allow-list (no dot)
          - pdf
          - xlsx

    Discovery is **shallow**: each seed URL is fetched once, parsed, and its
    ``<a href>`` links are extracted. Links are NOT followed recursively. To
    crawl, implement a dedicated ``Scraper`` subclass and register it in
    ``ingestion.scraper_factory``.
    """

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        timeout: int | None = None,
        html_fetcher: Callable[[str], str] | None = None,
    ):
        super().__init__(user_agent=user_agent, timeout=timeout)
        # Tests can inject a deterministic fetcher to avoid network.
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
        # We build the full validated list first, *then* slice by limit at the
        # end. That way the plan reports everything the user could ingest, not
        # just the first N — useful in dry-run for tuning ``--limit``.
        candidate_entries: list[ScraperPlanEntry] = []

        # 1) direct documents (explicit YAML entries)
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
                    "scraper.plan.direct_rejected url=%s reason=%s", url, reason
                )
                continue
            if url in seen_urls:
                plan.skipped_urls.append({"url": url, "reason": "duplicate"})
                continue
            seen_urls.add(url)
            plan.direct_urls.append(url)
            candidate_entries.append(
                ScraperPlanEntry(
                    url=url,
                    source="direct",
                    title=entry.get("title"),
                    document_type=entry.get("document_type"),
                    year=entry.get("year"),
                    metadata=entry.get("metadata") or {},
                )
            )

        # 2) seed URLs → fetch HTML → discover document links
        seed_urls = source_config.get("seed_urls") or []
        for seed in seed_urls:
            plan.seed_urls_checked.append(seed)
            try:
                html = self._fetch_html(seed)
            except Exception as e:
                logger.error(
                    "scraper.plan.seed_fetch_failed url=%s err=%r", seed, e
                )
                plan.skipped_urls.append(
                    {"url": seed, "reason": f"seed_fetch_failed:{e!r}"}
                )
                continue

            kept, skipped = extract_document_links(
                html,
                seed,
                allowed_domains=allowed_domains,
                document_extensions=document_extensions,
            )
            plan.skipped_urls.extend(skipped)
            if not kept and not skipped:
                # Zero <a href> elements that survived even the trivial filter.
                # Typical cause: the page is a SPA that renders links via JS,
                # so the static HTML has none. The user needs a different seed
                # URL or a dedicated scraper.
                plan.skipped_urls.append(
                    {"url": seed, "reason": "seed_no_anchors_found"}
                )
                logger.warning(
                    "scraper.plan.seed_no_anchors_found url=%s "
                    "(page may be JS-rendered)", seed
                )

            for url in kept:
                if url in seen_urls:
                    plan.skipped_urls.append({"url": url, "reason": "duplicate"})
                    continue
                seen_urls.add(url)
                plan.discovered_urls.append(url)
                candidate_entries.append(
                    ScraperPlanEntry(url=url, source="discovered")
                )

        # 3) cap fetch list at limit (direct first, discovered after — order preserved)
        plan.entries = candidate_entries[:limit]

        logger.info(
            "scraper.plan.done slug=%s direct=%d seeds=%d discovered=%d "
            "skipped=%d entries=%d (cap=%d)",
            slug,
            len(plan.direct_urls),
            len(plan.seed_urls_checked),
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
        """Plan then fetch each planned URL, yielding ScrapedDocument per success."""
        plan = self.plan(source_config, limit=limit)
        for entry in plan.entries:
            try:
                content, mime, ext = self.fetch(entry.url)
            except Exception as e:
                logger.error(
                    "scraper.fetch_failed url=%s err=%r", entry.url, e
                )
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

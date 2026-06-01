from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

EntrySource = Literal["direct", "discovered"]


@dataclass
class ScrapedDocument:
    """A fetched document, ready to be hashed and persisted."""

    content: bytes
    official_url: str
    mime_type: str
    extension: str
    title: str | None = None
    document_type: str | None = None
    year: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScraperPlanEntry:
    """One planned URL to fetch, with associated metadata."""

    url: str
    source: EntrySource = "direct"
    title: str | None = None
    document_type: str | None = None
    year: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScraperPlan:
    """The result of planning a scrape: which URLs would be fetched, and why others were skipped.

    Fields:
        direct_urls: URLs from explicit `direct_documents` (or legacy `documents`) that passed validation.
        seed_urls_checked: HTML seed URLs (generic scraper) that were fetched and parsed.
        content_pages_checked: SAPUMU content pages that were fetched and parsed.
        discovered_urls: URLs extracted from seeds / content pages that passed validation and dedup.
        skipped_urls: each entry is ``{"url": "...", "reason": "..."}``. Reasons include
            ``domain_not_allowed``, ``extension_not_allowed``, ``asset_extension``,
            ``no_extension``, ``non_http_scheme``, ``duplicate``, ``seed_fetch_failed:...``,
            ``content_fetch_failed:...``, ``no_level_content_found``,
            ``file_missing_full_url``, ``missing_url_in_entry``, ``seed_no_anchors_found``.
        entries: the ordered list of URLs that will actually be fetched (direct first,
            then discovered, deduplicated, capped at ``limit``).
    """

    direct_urls: list[str] = field(default_factory=list)
    seed_urls_checked: list[str] = field(default_factory=list)
    content_pages_checked: list[str] = field(default_factory=list)
    discovered_urls: list[str] = field(default_factory=list)
    skipped_urls: list[dict[str, str]] = field(default_factory=list)
    entries: list[ScraperPlanEntry] = field(default_factory=list)


class Scraper(Protocol):
    def plan(self, source_config: dict[str, Any], *, limit: int) -> ScraperPlan: ...

    def scrape(
        self, source_config: dict[str, Any], *, limit: int
    ) -> Iterable[ScrapedDocument]: ...

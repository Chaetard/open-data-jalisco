"""Convert discovered candidates into ScraperPlanEntry list, with filters.

This is the bridge between ``sapumu scan`` (offline discovery) and the
existing ``IngestSourceUseCase`` (download + persist). It is purely a
selection/projection layer:

- It does NOT fetch documents.
- It does NOT write to the DB.
- It does NOT touch docs/MANIFEST.md.
- It applies the same URL allow-listing that the SAPUMU scraper applies, so
  ingest behavior is identical whether the entry came from a live scrape or
  from a candidates JSON file.

It also encodes a small explicit allow-list / deny-list for *sensitive
content categories*. As of now, SAPUMU ``content_id=92`` carries
"declaraciones patrimoniales" (personal financial disclosures from public
servants). We don't ingest those by default — callers must pass
``allow_sensitive_content=True`` to override.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..adapters.scrapers._validation import is_url_allowed
from ..ports.scraper import ScraperPlanEntry

# Content IDs we refuse to ingest by default. Keep this list short and
# documented — every entry is a policy decision, not a heuristic.
SENSITIVE_CONTENT_IDS: frozenset[int] = frozenset(
    {
        92,  # declaraciones patrimoniales de servidores públicos
    }
)


class CandidateIngestError(Exception):
    """Raised for caller misuse (bad filter combo, etc.). Not for skipped URLs."""


@dataclass(frozen=True)
class CandidateIngestFilter:
    """Filters applied to candidates before turning them into plan entries.

    ``None`` on a scalar field disables that filter. ``content_title`` is a
    case-insensitive substring match. ``limit`` caps the final entries list
    after all other filtering, validation and dedup.
    """

    year: int | None = None
    extension: str | None = None
    content_id: int | None = None
    content_title: str | None = None
    limit: int = 10
    allow_sensitive_content: bool = False

    def matches(self, candidate: dict[str, Any]) -> bool:
        if self.year is not None and candidate.get("year") != self.year:
            return False
        if self.extension is not None:
            ext = candidate.get("extension")
            if (
                ext is None
                or str(ext).lower().lstrip(".") != self.extension.lower().lstrip(".")
            ):
                return False
        if self.content_id is not None and candidate.get("content_id") != self.content_id:
            return False
        if self.content_title is not None:
            title = candidate.get("content_title") or ""
            if self.content_title.lower() not in str(title).lower():
                return False
        return True


def select_entries(
    candidates: list[dict[str, Any]],
    *,
    filter_spec: CandidateIngestFilter,
    allowed_domains: list[str] | None,
    document_extensions: list[str] | None,
) -> tuple[list[ScraperPlanEntry], list[dict[str, str]]]:
    """Filter, validate and convert candidates into ``ScraperPlanEntry`` objects.

    Returns ``(entries, skipped)`` where:
    - ``entries`` is the ordered, deduplicated, capped list of plan entries
      ready to feed into ``IngestSourceUseCase.execute_from_entries``.
    - ``skipped`` is a list of ``{"url": "...", "reason": "..."}`` dicts. Reasons:
      ``filter_mismatch``, ``sensitive_content_id_blocked``, ``missing_url``,
      ``domain_not_allowed:<host>``, ``extension_not_allowed``,
      ``malformed_url:...``, ``duplicate``.

    The function is offline (no network, no DB). Idempotent for a given input.
    """
    if filter_spec.limit < 0:
        raise CandidateIngestError("limit must be >= 0")

    entries: list[ScraperPlanEntry] = []
    skipped: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        if not filter_spec.matches(candidate):
            continue

        content_id = candidate.get("content_id")
        if (
            isinstance(content_id, int)
            and content_id in SENSITIVE_CONTENT_IDS
            and not filter_spec.allow_sensitive_content
        ):
            skipped.append(
                {
                    "url": str(candidate.get("url") or ""),
                    "reason": f"sensitive_content_id_blocked:{content_id}",
                }
            )
            continue

        url = candidate.get("url")
        if not url:
            skipped.append({"url": "", "reason": "missing_url"})
            continue
        url = str(url)

        allowed, reason = is_url_allowed(
            url,
            allowed_domains=allowed_domains or None,
            document_extensions=document_extensions or None,
        )
        if not allowed:
            skipped.append({"url": url, "reason": reason})
            continue

        if url in seen_urls:
            skipped.append({"url": url, "reason": "duplicate"})
            continue
        seen_urls.add(url)

        entries.append(_candidate_to_plan_entry(candidate))

        if len(entries) >= filter_spec.limit:
            break

    return entries, skipped


def _candidate_to_plan_entry(candidate: dict[str, Any]) -> ScraperPlanEntry:
    """Mirror ``SapumuContentScraper._plan_entry_from_sapumu`` shape exactly.

    Keeping the metadata schema identical means documents ingested from a
    candidates file are indistinguishable downstream from documents ingested
    via a live SAPUMU scrape.
    """
    return ScraperPlanEntry(
        url=str(candidate["url"]),
        source="discovered",
        title=candidate.get("title") or candidate.get("file_name"),
        document_type=None,
        year=candidate.get("year"),
        metadata={
            "source_page": candidate.get("source_page"),
            "sapumu": {
                "content_id": candidate.get("content_id"),
                "content_title": candidate.get("content_title"),
                "slug": candidate.get("slug"),
                "date_at": candidate.get("date_at"),
                "file_name": candidate.get("file_name"),
                "mime_type": candidate.get("mime_type"),
                "size": candidate.get("size"),
                "extension": candidate.get("extension"),
                "month": candidate.get("month"),
                "year": candidate.get("year"),
            },
            "ingested_from": "candidates_file",
        },
    )

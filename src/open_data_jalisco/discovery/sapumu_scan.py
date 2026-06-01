# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 open-data-jalisco contributors

"""Conservative SAPUMU content-page discovery.

Iterates over an explicit ID range (``--from-id``..``--to-id``), fetches each
``content_page_template.format(id=N)`` once, parses the embedded JSON via
``adapters.scrapers._sapumu_parser`` and collects candidate document URLs.

Constraints by design:
- No DB writes. No PDF downloads.
- No URL guessing on the document bucket — we only consume URLs the SAPUMU
  page declares.
- A per-request delay (``--delay``) and an absolute range cap (``--max-range``)
  are enforced at the CLI layer to keep this conservative.
- The HTTP layer is injected via ``html_fetcher`` so tests stay offline.
"""
from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..adapters.scrapers._sapumu_parser import (
    extract_level_content_json,
    iter_files_from_content,
)
from ..adapters.scrapers._validation import is_url_allowed
from ..shared.logging import get_logger

logger = get_logger(__name__)


class SapumuScanError(Exception):
    """Raised for caller mistakes (invalid template, invalid range, etc.)."""


@dataclass
class SapumuScanConfig:
    """Inputs for one scan run."""

    template: str
    from_id: int
    to_id: int
    delay_seconds: float = 1.0
    allowed_domains: list[str] = field(default_factory=list)
    document_extensions: list[str] = field(default_factory=list)
    # Informational: which section (e.g. "articulo_8") this scan targets.
    # Used purely for reporting; the URL template already encodes it.
    section: str | None = None
    # If set, cap the number of IDs visited from the [from_id..to_id] range.
    limit_pages: int | None = None

    def validate(self) -> None:
        if "{id}" not in self.template:
            raise SapumuScanError(
                f"template must contain '{{id}}' placeholder: {self.template!r}"
            )
        if self.from_id < 1 or self.to_id < 1:
            raise SapumuScanError("from_id and to_id must be >= 1")
        if self.to_id < self.from_id:
            raise SapumuScanError("to_id must be >= from_id")
        if self.delay_seconds < 0:
            raise SapumuScanError("delay_seconds must be >= 0")
        if self.limit_pages is not None and self.limit_pages < 1:
            raise SapumuScanError("limit_pages must be >= 1 when set")

    @property
    def range_size(self) -> int:
        return self.to_id - self.from_id + 1

    @property
    def effective_page_count(self) -> int:
        if self.limit_pages is None:
            return self.range_size
        return min(self.range_size, self.limit_pages)

    def ids(self) -> list[int]:
        return list(range(self.from_id, self.from_id + self.effective_page_count))

    def urls(self) -> list[str]:
        return [self.template.format(id=i) for i in self.ids()]


@dataclass
class SapumuFileCandidate:
    url: str
    title: str | None
    slug: str | None
    date_at: str | None
    file_name: str | None
    mime_type: str | None
    size: int | None
    extension: str | None
    year: int | None
    month: int | None
    content_id: int | None
    content_title: str | None
    source_page: str


@dataclass
class SapumuScanResult:
    template: str
    from_id: int
    to_id: int
    delay_seconds: float = 0.0
    dry_run: bool = False
    section: str | None = None
    limit_pages: int | None = None
    pages_checked: int = 0
    # Pages that returned a parseable <level-content> payload (whether or not
    # any files were attached). Superset of ``pages_with_documents``.
    pages_found: int = 0
    pages_with_documents: int = 0
    pages_no_documents: int = 0
    pages_failed: int = 0
    documents_found: int = 0
    candidates: list[SapumuFileCandidate] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def sample_documents(self, n: int = 5) -> list[dict[str, Any]]:
        """Return the first ``n`` candidates as plain dicts for summaries."""
        return [asdict(c) for c in self.candidates[:n]]


def scan_content_pages(
    config: SapumuScanConfig,
    *,
    html_fetcher: Callable[[str], str],
    sleep: Callable[[float], None] = time.sleep,
) -> SapumuScanResult:
    """Execute one scan run. ``html_fetcher`` is the only network seam.

    No exceptions from ``html_fetcher`` propagate — they're recorded as
    ``errors`` on the result so a single 500 doesn't abort the batch.
    """
    config.validate()

    result = SapumuScanResult(
        template=config.template,
        from_id=config.from_id,
        to_id=config.to_id,
        delay_seconds=config.delay_seconds,
        section=config.section,
        limit_pages=config.limit_pages,
    )
    seen_urls: set[str] = set()

    for index, content_id in enumerate(config.ids()):
        if index > 0 and config.delay_seconds > 0:
            sleep(config.delay_seconds)

        page_url = config.template.format(id=content_id)
        result.pages_checked += 1
        try:
            html = html_fetcher(page_url)
        except Exception as e:
            result.pages_failed += 1
            result.errors.append({"page": page_url, "error": repr(e)[:300]})
            logger.warning("sapumu.scan.fetch_failed url=%s err=%r", page_url, e)
            continue

        content_data = extract_level_content_json(html)
        if content_data is None:
            result.pages_no_documents += 1
            logger.debug("sapumu.scan.no_level_content url=%s", page_url)
            continue

        # Page exists and is a SAPUMU content page — count it as found even
        # if no document URLs are attached yet.
        result.pages_found += 1
        page_doc_count = 0
        for file_entry in iter_files_from_content(content_data):
            url = file_entry.get("full_url")
            if not url:
                result.skipped.append({"url": "", "reason": "file_missing_full_url"})
                continue
            allowed, reason = is_url_allowed(
                url,
                allowed_domains=config.allowed_domains or None,
                document_extensions=config.document_extensions or None,
            )
            if not allowed:
                result.skipped.append({"url": url, "reason": reason})
                continue
            if url in seen_urls:
                result.skipped.append({"url": url, "reason": "duplicate"})
                continue
            seen_urls.add(url)
            result.candidates.append(
                SapumuFileCandidate(
                    url=url,
                    title=file_entry.get("title"),
                    slug=file_entry.get("slug"),
                    date_at=file_entry.get("date_at"),
                    file_name=file_entry.get("file_name"),
                    mime_type=file_entry.get("mime_type"),
                    size=file_entry.get("size"),
                    extension=file_entry.get("extension"),
                    year=file_entry.get("year"),
                    month=file_entry.get("month"),
                    content_id=file_entry.get("content_id"),
                    content_title=file_entry.get("content_title"),
                    source_page=page_url,
                )
            )
            page_doc_count += 1
            result.documents_found += 1

        if page_doc_count > 0:
            result.pages_with_documents += 1
        else:
            result.pages_no_documents += 1

    logger.info(
        "sapumu.scan.done template=%s from=%d to=%d checked=%d with_docs=%d "
        "no_docs=%d failed=%d found=%d skipped=%d",
        config.template,
        config.from_id,
        config.to_id,
        result.pages_checked,
        result.pages_with_documents,
        result.pages_no_documents,
        result.pages_failed,
        result.documents_found,
        len(result.skipped),
    )
    return result


def export_candidates(result: SapumuScanResult, path: Path) -> None:
    """Write candidates + summary to ``path``. Format inferred from extension.

    Supports ``.json``, ``.yaml`` and ``.yml``.
    """
    payload: dict[str, Any] = {
        "template": result.template,
        "section": result.section,
        "from_id": result.from_id,
        "to_id": result.to_id,
        "limit_pages": result.limit_pages,
        "delay_seconds": result.delay_seconds,
        "pages_checked": result.pages_checked,
        "pages_found": result.pages_found,
        "pages_with_documents": result.pages_with_documents,
        "pages_no_documents": result.pages_no_documents,
        "pages_failed": result.pages_failed,
        "documents_found": result.documents_found,
        "candidates": [asdict(c) for c in result.candidates],
        "skipped": result.skipped,
        "errors": result.errors,
    }

    ext = path.suffix.lower().lstrip(".")
    path.parent.mkdir(parents=True, exist_ok=True)
    if ext in {"yaml", "yml"}:
        path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    elif ext == "json":
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    else:
        raise SapumuScanError(
            f"unsupported output format: {ext!r} (use .json or .yaml/.yml)"
        )

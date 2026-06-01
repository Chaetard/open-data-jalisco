from typing import Any

from ..adapters.scrapers import GenericHttpScraper, SapumuContentScraper
from ..ports.scraper import Scraper


class UnknownScraperError(Exception):
    pass


def build_scraper(
    scraper_config: dict[str, Any],
    *,
    timeout: int | None = None,
    user_agent: str | None = None,
) -> Scraper:
    scraper_type = (scraper_config or {}).get("type", "generic_http")
    if scraper_type == "generic_http":
        return GenericHttpScraper(user_agent=user_agent, timeout=timeout)
    if scraper_type == "sapumu_content":
        return SapumuContentScraper(user_agent=user_agent, timeout=timeout)
    raise UnknownScraperError(
        f"Unknown scraper type: {scraper_type!r}. "
        "Implement a Scraper and register it here."
    )

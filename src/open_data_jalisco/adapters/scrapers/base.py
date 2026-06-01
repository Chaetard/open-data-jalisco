from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ...ports.scraper import ScrapedDocument
from ...shared.config import get_settings
from ...shared.logging import get_logger

logger = get_logger(__name__)


_EXT_BY_MIME = {
    "application/pdf": "pdf",
    "text/html": "html",
    "application/xhtml+xml": "html",
    "text/plain": "txt",
    "text/csv": "csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}


class HttpScraper:
    """Reusable HTTP downloader with retry + UA. Subclass or compose for source-specific logic."""

    def __init__(self, *, user_agent: str | None = None, timeout: int | None = None):
        settings = get_settings()
        self._user_agent = user_agent or settings.scraper_user_agent
        self._timeout = timeout or settings.scraper_timeout_seconds
        self._max_retries = settings.scraper_max_retries
        self._backoff = settings.scraper_retry_backoff_seconds

    def _client(self) -> httpx.Client:
        return httpx.Client(
            headers={"User-Agent": self._user_agent},
            timeout=self._timeout,
            follow_redirects=True,
        )

    def fetch(self, url: str) -> tuple[bytes, str, str]:
        """Returns (content, mime_type, extension). Retries transient failures."""

        @retry(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=self._backoff, min=self._backoff, max=30),
            retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
            reraise=True,
        )
        def _do() -> tuple[bytes, str, str]:
            with self._client() as client:
                logger.info("scraper.fetch url=%s", url)
                response = client.get(url)
                response.raise_for_status()
                mime = (response.headers.get("content-type", "").split(";")[0] or "").strip()
                if not mime:
                    mime = "application/octet-stream"
                ext = _EXT_BY_MIME.get(mime) or _guess_extension_from_url(url)
                return response.content, mime, ext

        return _do()

    def scrape(self, source_config: dict[str, Any]) -> Iterable[ScrapedDocument]:
        raise NotImplementedError(
            "HttpScraper is a base utility. Subclass it or use GenericHttpScraper for direct URLs."
        )


def _guess_extension_from_url(url: str) -> str:
    path = urlparse(url).path.rsplit(".", 1)
    if len(path) == 2 and 1 <= len(path[1]) <= 6:
        return path[1].lower()
    return "bin"

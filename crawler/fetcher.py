"""
crawler/fetcher.py — Async HTTP fetcher với hishel cache và retry tự động
"""
import asyncio
from typing import Optional

import httpx
import hishel

from config import (
    CACHE_DIR, CACHE_TTL, REQUEST_TIMEOUT,
    RETRY_COUNT, RETRY_BACKOFF, USER_AGENT,
)
from utils.logger import log_error, log_skip, setup_logger

logger = setup_logger()

_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class PageResult:
    """Kết quả fetch một trang."""
    def __init__(self, url: str, html: str = "", status: int = 0, skipped: bool = False, reason: str = ""):
        self.url = url
        self.html = html
        self.status = status
        self.skipped = skipped
        self.reason = reason


class AsyncFetcher:
    """
    Async HTTP client với:
    - hishel cache (SQLite backend, TTL 24h) nếu enabled
    - asyncio.Semaphore cho rate limiting
    - Auto retry với exponential backoff
    """

    def __init__(self, concurrency: int = 5, use_cache: bool = False):
        self.semaphore = asyncio.Semaphore(concurrency)
        self.use_cache = use_cache
        self._client: Optional[httpx.AsyncClient] = None
        self._storage: Optional[hishel.AsyncFileStorage] = None

    async def __aenter__(self):
        if self.use_cache:
            self._storage = hishel.AsyncFileStorage(
                base_path=CACHE_DIR,
                ttl=CACHE_TTL,
            )
            controller = hishel.Controller(
                cacheable_methods=["GET"],
                cacheable_status_codes=[200],
                allow_stale=False,
            )
            transport = hishel.AsyncCacheTransport(
                transport=httpx.AsyncHTTPTransport(retries=0),
                storage=self._storage,
                controller=controller,
            )
            self._client = httpx.AsyncClient(
                headers=_HEADERS,
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                transport=transport,
            )
        else:
            self._client = httpx.AsyncClient(
                headers=_HEADERS,
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
            )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    async def fetch(self, url: str) -> PageResult:
        """Fetch một URL với rate limiting và retry. Thread-safe với semaphore."""
        async with self.semaphore:
            for attempt in range(1, RETRY_COUNT + 1):
                try:
                    resp = await self._client.get(url)

                    if resp.status_code == 403:
                        log_skip(logger, url, f"HTTP 403 Forbidden")
                        return PageResult(url, skipped=True, reason="403 Forbidden", status=403)

                    if resp.status_code == 404:
                        log_skip(logger, url, f"HTTP 404 Not Found")
                        return PageResult(url, skipped=True, reason="404 Not Found", status=404)

                    if resp.status_code >= 400:
                        if attempt == RETRY_COUNT:
                            log_skip(logger, url, f"HTTP {resp.status_code}")
                            return PageResult(url, skipped=True, reason=f"HTTP {resp.status_code}", status=resp.status_code)
                        await asyncio.sleep(RETRY_BACKOFF * attempt)
                        continue

                    return PageResult(url, html=resp.text, status=resp.status_code)

                except httpx.TimeoutException:
                    if attempt == RETRY_COUNT:
                        log_skip(logger, url, "Timeout sau 3 lần thử")
                        return PageResult(url, skipped=True, reason="Timeout")
                    await asyncio.sleep(RETRY_BACKOFF * attempt)

                except Exception as e:
                    if attempt == RETRY_COUNT:
                        log_error(logger, url, e)
                        return PageResult(url, skipped=True, reason=str(e))
                    await asyncio.sleep(RETRY_BACKOFF * attempt)

            return PageResult(url, skipped=True, reason="Max retries exceeded")

    async def fetch_all(self, urls: list[str], progress_callback=None) -> list[PageResult]:
        """Fetch tất cả URLs song song (giới hạn bởi semaphore)."""
        tasks = [self.fetch(url) for url in urls]
        results = []

        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            if progress_callback:
                progress_callback()

        # Sắp xếp lại theo thứ tự ban đầu
        url_order = {url: i for i, url in enumerate(urls)}
        results.sort(key=lambda r: url_order.get(r.url, 9999))
        return results

"""Async httpx client for the Danish Retsinformation API (retsinformation.dk) with cache.

Two hosts, both keyless (Open Data):
- ``www.retsinformation.dk`` - ELI XML/HTML for full documents
  (``/eli/lta/{year}/{number}/xml`` and ``/eli/accn/{accession}/xml``).
- ``api.retsinformation.dk`` - the harvest API ``/v1/Documents?date=YYYY-MM-DD`` (JSON),
  available 03:00-23:45 Danish time, listing documents changed on a date.

We keep our own backoff + cache.
"""

from __future__ import annotations

from typing import Any

import anyio
import httpx

from .cache import HttpCache

DEFAULT_BASE_URL = "https://www.retsinformation.dk"
DEFAULT_API_URL = "https://api.retsinformation.dk"
DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
USER_AGENT = "dk-eli-mcp/0.1.0 (+https://github.com/matematicsolutions/dk-eli-mcp)"

_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
_MAX_ATTEMPTS = 3


class RetsinfoClient:
    """Async client. Use as ``async with RetsinfoClient() as c: ...``."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_url: str = DEFAULT_API_URL,
        cache: HttpCache | None = None,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_url = api_url.rstrip("/")
        self._cache = cache or HttpCache()
        self._http = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    async def __aenter__(self) -> RetsinfoClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()
        self._cache.close()

    async def _get(self, url: str, *, accept: str, category: str) -> str:
        cached = self._cache.get(url)
        if cached is not None and isinstance(cached, str):
            return cached
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                resp = await self._http.get(url, headers={"Accept": accept})
                resp.raise_for_status()
                self._cache.set(url, resp.text, ttl=HttpCache.ttl_for(category))
                return resp.text
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code not in _RETRY_STATUS or attempt == _MAX_ATTEMPTS - 1:
                    raise
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt == _MAX_ATTEMPTS - 1:
                    raise
            await anyio.sleep(0.5 * (2**attempt))
        assert last_exc is not None
        raise last_exc

    async def get_act_xml(self, year: int, number: int) -> str:
        """Fetch a document's LexDania XML by ELI coordinate (lta = Lovtidende A)."""
        url = f"{self.base_url}/eli/lta/{year}/{number}/xml"
        return await self._get(url, accept="application/xml", category="act")

    async def get_act_xml_by_accession(self, accession: str) -> str:
        """Fetch a document's LexDania XML by accession number."""
        url = f"{self.base_url}/eli/accn/{accession}/xml"
        return await self._get(url, accept="application/xml", category="act")

    async def recent_changes(self, date: str) -> list[dict[str, Any]]:
        """List documents changed on a date via the harvest API.

        ``date`` is ``YYYY-MM-DD``. Returns the raw JSON list (possibly empty).
        """
        url = f"{self.api_url}/v1/Documents?date={date}"
        text = await self._get(url, accept="application/json", category="changes")
        import json

        data = json.loads(text)
        if isinstance(data, list):
            return data
        if data:
            return [data]
        return []

from __future__ import annotations

import time
from typing import Dict, Optional

import httpx

from .cache import LastModifiedCache


class HttpFetcher:
    """HTTP client wrapper with retry/backoff and Last-Modified caching."""

    def __init__(
        self,
        client: Optional[httpx.Client] = None,
        *,
        max_attempts: int = 3,
        backoff_factor: float = 0.5,
        cache: Optional[LastModifiedCache] = None,
    ) -> None:
        self.client = client or httpx.Client(timeout=10.0)
        self.max_attempts = max_attempts
        self.backoff_factor = backoff_factor
        self.cache = cache or LastModifiedCache()

    def fetch(self, url: str, *, extra_headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        headers: Dict[str, str] = {}
        headers.update(self.cache.get_conditional_headers(url))
        if extra_headers:
            headers.update(extra_headers)

        last_error: Optional[Exception] = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.client.get(url, headers=headers)
                return response
            except httpx.RequestError as exc:  # pragma: no cover - network failure path
                last_error = exc
                if attempt == self.max_attempts:
                    raise
                sleep_for = self.backoff_factor * (2 ** (attempt - 1))
                time.sleep(sleep_for)
        if last_error:
            raise last_error
        raise RuntimeError("Unexpected fetch state")

from __future__ import annotations

from typing import Callable, Dict, Tuple

import httpx

from ..cache import LastModifiedCache
from ..http_client import HttpFetcher
from ..models import ConditionSnapshot
from . import alpine_peak, summit_valley

Scraper = Tuple[str, Callable[[str], ConditionSnapshot]]

SCRAPERS: Dict[str, Scraper] = {
    alpine_peak.RESORT_ID: (alpine_peak.REPORT_URL, alpine_peak.parse_conditions),
    summit_valley.RESORT_ID: (summit_valley.REPORT_URL, summit_valley.parse_conditions),
}


def fetch_conditions(
    resort_id: str,
    *,
    client: httpx.Client | None = None,
    cache: LastModifiedCache | None = None,
) -> ConditionSnapshot:
    if resort_id not in SCRAPERS:
        raise KeyError(f"Unknown resort_id: {resort_id}")

    url, parser = SCRAPERS[resort_id]
    fetcher = HttpFetcher(client=client, cache=cache)
    response = fetcher.fetch(url)

    cached_snapshot = fetcher.cache.get_snapshot(url)
    if response.status_code == 304:
        if cached_snapshot:
            return cached_snapshot
        raise RuntimeError("Received 304 but no cached snapshot is available")

    response.raise_for_status()
    snapshot = parser(response.text)
    fetcher.cache.update(url, response.headers.get("Last-Modified"), snapshot)
    return snapshot

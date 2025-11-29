from __future__ import annotations

from functools import partial
from typing import Callable, Dict, Tuple
import uuid

import httpx

from snow_day.config import ScraperSettings, app_config
from snow_day.logging import get_logger

from ..cache import LastModifiedCache
from ..http_client import HttpFetcher
from ..models import ConditionSnapshot
from . import alpine_peak, summit_valley

logger = get_logger(__name__)

Scraper = Tuple[str, Callable[[str], ConditionSnapshot]]

_PARSERS: Dict[str, Callable[..., ConditionSnapshot]] = {
    alpine_peak.RESORT_ID: alpine_peak.parse_conditions,
    summit_valley.RESORT_ID: summit_valley.parse_conditions,
}


def _settings_for(resort_id: str) -> ScraperSettings:
    defaults = None
    if resort_id == alpine_peak.RESORT_ID:
        defaults = ScraperSettings(
            report_url=alpine_peak.DEFAULT_REPORT_URL,
            selectors=dict(alpine_peak.DEFAULT_SELECTORS),
        )
    elif resort_id == summit_valley.RESORT_ID:
        defaults = ScraperSettings(
            report_url=summit_valley.DEFAULT_REPORT_URL,
            selectors=dict(summit_valley.DEFAULT_SELECTORS),
        )
    configured = app_config.scrapers.get(resort_id)
    if not configured:
        return defaults or ScraperSettings()
    if defaults:
        merged_selectors = {**defaults.selectors, **configured.selectors}
        return ScraperSettings(report_url=configured.report_url or defaults.report_url, selectors=merged_selectors)
    return configured


def _build_scrapers() -> Dict[str, Scraper]:
    scrapers: Dict[str, Scraper] = {}
    for resort in app_config.resorts:
        scraper_id = resort.scraper or resort.id
        parser = _PARSERS.get(scraper_id)
        settings = _settings_for(scraper_id)
        if not parser or not settings.report_url:
            continue
        scrapers[resort.id] = (
            settings.report_url,
            partial(parser, selectors=settings.selectors),
        )
    return scrapers


SCRAPERS: Dict[str, Scraper] = _build_scrapers()


def fetch_conditions(
    resort_id: str,
    *,
    client: httpx.Client | None = None,
    cache: LastModifiedCache | None = None,
    trace_id: str | None = None,
) -> ConditionSnapshot:
    trace_id = trace_id or uuid.uuid4().hex
    if resort_id not in SCRAPERS:
        logger.error("scrape.unknown_resort", trace_id=trace_id, resort_id=resort_id)
        raise KeyError(f"Unknown resort_id: {resort_id}")

    url, parser = SCRAPERS[resort_id]
    fetcher = HttpFetcher(client=client, cache=cache)
    logger.info("scrape.request", trace_id=trace_id, resort_id=resort_id, url=url)
    try:
        response = fetcher.fetch(url, trace_id=trace_id)
        cached_snapshot = fetcher.cache.get_snapshot(url)
        if response.status_code == 304:
            if cached_snapshot:
                logger.info(
                    "scrape.cache_hit",
                    trace_id=trace_id,
                    resort_id=resort_id,
                    url=url,
                )
                return cached_snapshot
            raise RuntimeError("Received 304 but no cached snapshot is available")

        response.raise_for_status()
        snapshot = parser(response.text)
        fetcher.cache.update(url, response.headers.get("Last-Modified"), snapshot)
        logger.info(
            "scrape.success",
            trace_id=trace_id,
            resort_id=resort_id,
            url=url,
            status_code=response.status_code,
        )
        return snapshot
    except Exception as exc:
        logger.error(
            "scrape.failure",
            trace_id=trace_id,
            resort_id=resort_id,
            url=url,
            error=str(exc),
        )
        raise

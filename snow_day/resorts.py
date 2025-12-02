from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from snow_day.config import app_config


@dataclass
class ResortMeta:
    """Lightweight metadata for known resorts."""

    id: str
    name: str
    state: str
    report_url: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


def all_resorts() -> List[ResortMeta]:
    """Build a list of resorts using configured scraper report URLs."""

    resorts: List[ResortMeta] = []
    for resort in app_config.resorts:
        scraper_id = resort.scraper or resort.id
        scraper_settings = app_config.scrapers.get(scraper_id)
        report_url = scraper_settings.report_url if scraper_settings else ""
        resorts.append(
            ResortMeta(
                id=resort.id,
                name=resort.name,
                state=resort.state,
                report_url=report_url,
                latitude=resort.latitude,
                longitude=resort.longitude,
            )
        )
    return resorts


def resort_lookup(resorts: Iterable[ResortMeta]) -> Dict[str, ResortMeta]:
    return {resort.id: resort for resort in resorts}

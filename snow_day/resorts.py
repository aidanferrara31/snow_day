from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

RESORT_DISPLAY: Dict[str, str] = {
    "alpine_peak": "Alpine Peak",
    "summit_valley": "Summit Valley",
}


@dataclass
class ResortMeta:
    """Lightweight metadata for known resorts."""

    id: str
    name: str
    state: str
    report_url: str


def all_resorts(report_urls: Dict[str, str]) -> List[ResortMeta]:
    """Build a list of resorts using known scraper report URLs."""

    resorts: List[ResortMeta] = []
    for resort_id, url in report_urls.items():
        name = RESORT_DISPLAY.get(resort_id, resort_id.replace("_", " ").title())
        state = "CO" if "alpine" in resort_id else "WA"
        resorts.append(ResortMeta(id=resort_id, name=name, state=state, report_url=url))
    return resorts


def resort_lookup(resorts: Iterable[ResortMeta]) -> Dict[str, ResortMeta]:
    return {resort.id: resort for resort in resorts}


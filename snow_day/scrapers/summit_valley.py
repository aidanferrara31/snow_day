"""Scraper for Summit Valley (example/template scraper).

This is a configurable scraper that uses CSS selectors defined in config.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, Mapping, MutableMapping, Optional

from bs4 import BeautifulSoup

from ..models import ConditionSnapshot
from ..normalization import DEFAULT_NORMALIZER
from .base import create_soup, extract_numeric

RESORT_ID = "summit_valley"
DEFAULT_REPORT_URL = "https://example.com/summit-valley/conditions"

DEFAULT_SELECTORS: MutableMapping[str, str] = {
    "wind": ".conditions .wind",
    "base": ".conditions .base",
    "snowfall_12h": ".conditions .snowfall .h12",
    "snowfall_24h": ".conditions .snowfall .h24",
    "snowfall_7d": ".conditions .snowfall .d7",
    "temps_table": "table.temps tr",
    "lifts_table": "table.lifts tr",
    "lift_name_attr": "data-name",
    "lift_status_attr": "data-status",
}


def _extract_float(text: str) -> Optional[float]:
    """Extract float from text, return None if not found."""
    if not text:
        return None
    return extract_numeric(text)


def parse_conditions(html: str, *, selectors: Mapping[str, str] | None = None) -> ConditionSnapshot:
    """Parse snow report HTML using configurable selectors."""
    active_selectors: Dict[str, str] = {**DEFAULT_SELECTORS, **(selectors or {})}
    soup = create_soup(html)

    wind_speed = None
    wind_direction = None
    wind_selector = active_selectors.get("wind")
    if wind_selector:
        wind_node = soup.select_one(wind_selector)
        if wind_node:
            wind_text = wind_node.get_text()
            match = re.search(r"(?P<direction>[A-Z]{1,3})\s+at\s+(?P<speed>\d+(?:\.\d+)?)", wind_text, re.IGNORECASE)
            if match:
                wind_speed = float(match.group("speed"))
                wind_direction = match.group("direction")

    base_depth = None
    base_selector = active_selectors.get("base")
    if base_selector:
        base_node = soup.select_one(base_selector)
        if base_node:
            base_depth = _extract_float(base_node.get_text())

    snowfall: Dict[str, Optional[float]] = {"12h": None, "24h": None, "7d": None}
    
    snowfall_12h_node = soup.select_one(active_selectors.get("snowfall_12h", ""))
    snowfall_24h_node = soup.select_one(active_selectors.get("snowfall_24h", ""))
    snowfall_7d_node = soup.select_one(active_selectors.get("snowfall_7d", ""))
    
    if snowfall_12h_node:
        snowfall["12h"] = _extract_float(snowfall_12h_node.get_text())
    if snowfall_24h_node:
        snowfall["24h"] = _extract_float(snowfall_24h_node.get_text())
    if snowfall_7d_node:
        snowfall["7d"] = _extract_float(snowfall_7d_node.get_text())

    temps: Dict[str, Optional[float]] = {"low": None, "high": None}
    temps_selector = active_selectors.get("temps_table")
    if temps_selector:
        for row in soup.select(temps_selector):
            th = row.select_one("th")
            td = row.select_one("td")
            if th and td:
                key = th.get_text(strip=True).lower()
                temps[key] = _extract_float(td.get_text())

    lift_status: Dict[str, str] = {}
    lifts_selector = active_selectors.get("lifts_table")
    if lifts_selector:
        for row in soup.select(lifts_selector):
            name = row.get(active_selectors.get("lift_name_attr", ""), row.get_text(strip=True))
            status = row.get(active_selectors.get("lift_status_attr", ""), row.get_text(strip=True))
            if name:
                lift_status[name] = status.lower() if status else ""

    lifts_open = sum(1 for status in lift_status.values() if status == "open")
    lifts_total = len(lift_status) if lift_status else None

    raw_metrics = {
        "wind_speed_mph": wind_speed,
        "wind_chill_f": None,
        "temp_low_f": temps.get("low"),
        "temp_high_f": temps.get("high"),
        "snowfall_last_12h_in": snowfall["12h"],
        "snowfall_last_24h_in": snowfall["24h"],
        "snowfall_last_7d_in": snowfall["7d"],
        "base_depth_in": base_depth,
        "precip_type": None,
    }

    snapshot = DEFAULT_NORMALIZER.normalize(
        RESORT_ID, raw_metrics, timestamp=datetime.now(timezone.utc)
    )
    return snapshot

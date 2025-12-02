"""Scraper for Alpine Peak (example/template scraper).

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

RESORT_ID = "alpine_peak"
DEFAULT_REPORT_URL = "https://example.com/alpine-peak/snow-report"

DEFAULT_SELECTORS: MutableMapping[str, str] = {
    "snowfall": "section#snowfall .metric",
    "snowfall_period_attr": "data-period",
    "low_temp": "section#temperatures .low-temp",
    "high_temp": "section#temperatures .high-temp",
    "wind": "section#wind",
    "base": "section#base",
    "lift_counts": "section#lifts .counts",
    "lift_open": ".open",
    "lift_total": ".total",
    "lifts": "section#lifts .lift-status li",
    "lift_name_attr": "data-name",
    "lift_status_attr": "data-status",
}


def _extract_float(text: str) -> Optional[float]:
    """Extract float from text, return None if not found."""
    if not text:
        return None
    result = extract_numeric(text)
    return result


def parse_conditions(html: str, *, selectors: Mapping[str, str] | None = None) -> ConditionSnapshot:
    """Parse snow report HTML using configurable selectors."""
    active_selectors: Dict[str, str] = {**DEFAULT_SELECTORS, **(selectors or {})}
    soup = create_soup(html)

    snowfall_values: Dict[str, float] = {}
    for node in soup.select(active_selectors["snowfall"]):
        period = node.get(active_selectors["snowfall_period_attr"])
        value = _extract_float(node.get_text())
        if period and value is not None:
            snowfall_values[period] = value

    low_temp = None
    high_temp = None
    low_temp_node = soup.select_one(active_selectors["low_temp"])
    high_temp_node = soup.select_one(active_selectors["high_temp"])
    if low_temp_node:
        low_temp = _extract_float(low_temp_node.get_text())
    if high_temp_node:
        high_temp = _extract_float(high_temp_node.get_text())

    wind_speed = None
    wind_direction = None
    wind_selector = active_selectors.get("wind")
    if wind_selector:
        wind_section = soup.select_one(wind_selector)
        if wind_section:
            wind_text = wind_section.get_text()
            wind_match = re.search(r"(?P<speed>\d+(?:\.\d+)?)\s*mph\s*(?P<direction>[A-Z]+)?", wind_text, re.IGNORECASE)
            if wind_match:
                wind_speed = float(wind_match.group("speed"))
                wind_direction = wind_match.group("direction")

    base_depth = None
    base_selector = active_selectors.get("base")
    if base_selector:
        base_node = soup.select_one(base_selector)
        if base_node:
            base_depth = _extract_float(base_node.get_text())

    lifts_open = None
    lifts_total = None
    counts_selector = active_selectors.get("lift_counts")
    if counts_selector:
        counts = soup.select_one(counts_selector)
        if counts:
            open_selector = active_selectors.get("lift_open")
            total_selector = active_selectors.get("lift_total")
            if open_selector and total_selector:
                open_node = counts.select_one(open_selector)
                total_node = counts.select_one(total_selector)
                if open_node and total_node:
                    open_val = _extract_float(open_node.get_text())
                    total_val = _extract_float(total_node.get_text())
                    if open_val is not None:
                        lifts_open = int(open_val)
                    if total_val is not None:
                        lifts_total = int(total_val)

    timestamp = datetime.now(timezone.utc)
    raw_metrics = {
        "wind_speed_mph": wind_speed,
        "wind_chill_f": None,
        "temp_low_f": low_temp,
        "temp_high_f": high_temp,
        "snowfall_last_12h_in": snowfall_values.get("12h"),
        "snowfall_last_24h_in": snowfall_values.get("24h"),
        "snowfall_last_7d_in": snowfall_values.get("7d"),
        "base_depth_in": base_depth,
        "precip_type": None,
    }

    snapshot = DEFAULT_NORMALIZER.normalize(
        RESORT_ID,
        raw_metrics,
        timestamp=timestamp,
    )

    return snapshot

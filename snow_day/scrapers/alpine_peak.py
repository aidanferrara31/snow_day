from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, Mapping, MutableMapping

from selectolax.parser import HTMLParser

from ..models import ConditionSnapshot
from ..normalization import DEFAULT_NORMALIZER

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


def _extract_float(text: str) -> float:
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not match:
        raise ValueError(f"No numeric value in '{text}'")
    return float(match.group(1))


def parse_conditions(html: str, *, selectors: Mapping[str, str] | None = None) -> ConditionSnapshot:
    active_selectors: Dict[str, str] = {**DEFAULT_SELECTORS, **(selectors or {})}
    tree = HTMLParser(html)

    snowfall_values: Dict[str, float] = {}
    for node in tree.css(active_selectors["snowfall"]):
        period = node.attributes.get(active_selectors["snowfall_period_attr"])
        value = _extract_float(node.text())
        if period:
            snowfall_values[period] = value

    low_temp = _extract_float(tree.css_first(active_selectors["low_temp"]).text())
    high_temp = _extract_float(tree.css_first(active_selectors["high_temp"]).text())

    wind_section = tree.css_first(active_selectors["wind"]) if active_selectors.get("wind") else None
    wind_speed = None
    wind_direction = None
    if wind_section:
        wind_text = wind_section.text()
        wind_match = re.search(r"(?P<speed>\d+(?:\.\d+)?)\s*mph\s*(?P<direction>[A-Z]+)?", wind_text, re.IGNORECASE)
        if wind_match:
            wind_speed = float(wind_match.group("speed"))
            wind_direction = wind_match.group("direction")

    base_depth = None
    base_selector = active_selectors.get("base")
    if base_selector:
        base_node = tree.css_first(base_selector)
        if base_node:
            base_depth = _extract_float(base_node.text())

    lifts_open = None
    lifts_total = None
    counts_selector = active_selectors.get("lift_counts")
    if counts_selector:
        counts = tree.css_first(counts_selector)
        if counts:
            open_selector = active_selectors.get("lift_open")
            total_selector = active_selectors.get("lift_total")
            if open_selector and total_selector:
                open_node = counts.css_first(open_selector)
                total_node = counts.css_first(total_selector)
                if open_node and total_node:
                    lifts_open = int(_extract_float(open_node.text()))
                    lifts_total = int(_extract_float(total_node.text()))

    lift_status: Dict[str, str] = {}
    lifts_selector = active_selectors.get("lifts")
    if lifts_selector:
        for node in tree.css(lifts_selector):
            name = node.attributes.get(active_selectors.get("lift_name_attr", ""), node.text(strip=True))
            status = node.attributes.get(active_selectors.get("lift_status_attr", ""), node.text(strip=True))
            lift_status[name] = status.lower()

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

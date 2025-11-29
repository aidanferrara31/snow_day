from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict

from selectolax.parser import HTMLParser

from ..models import ConditionSnapshot
from ..normalization import DEFAULT_NORMALIZER

RESORT_ID = "alpine_peak"
REPORT_URL = "https://example.com/alpine-peak/snow-report"


def _extract_float(text: str) -> float:
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not match:
        raise ValueError(f"No numeric value in '{text}'")
    return float(match.group(1))


def parse_conditions(html: str) -> ConditionSnapshot:
    tree = HTMLParser(html)

    snowfall_values: Dict[str, float] = {}
    for node in tree.css("section#snowfall .metric"):
        period = node.attributes.get("data-period")
        value = _extract_float(node.text())
        snowfall_values[period] = value

    low_temp = _extract_float(tree.css_first("section#temperatures .low-temp").text())
    high_temp = _extract_float(tree.css_first("section#temperatures .high-temp").text())

    wind_section = tree.css_first("section#wind")
    wind_speed = None
    wind_direction = None
    if wind_section:
        wind_text = wind_section.text()
        wind_match = re.search(r"(?P<speed>\d+(?:\.\d+)?)\s*mph\s*(?P<direction>[A-Z]+)?", wind_text, re.IGNORECASE)
        if wind_match:
            wind_speed = float(wind_match.group("speed"))
            wind_direction = wind_match.group("direction")

    base_depth = None
    base_node = tree.css_first("section#base")
    if base_node:
        base_depth = _extract_float(base_node.text())

    lifts_open = None
    lifts_total = None
    counts = tree.css_first("section#lifts .counts")
    if counts:
        open_node = counts.css_first(".open")
        total_node = counts.css_first(".total")
        if open_node and total_node:
            lifts_open = int(_extract_float(open_node.text()))
            lifts_total = int(_extract_float(total_node.text()))

    lift_status: Dict[str, str] = {}
    for node in tree.css("section#lifts .lift-status li"):
        name = node.attributes.get("data-name", node.text(strip=True))
        status = node.attributes.get("data-status", node.text(strip=True))
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

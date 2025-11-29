from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict

from selectolax.parser import HTMLParser

from ..models import ConditionSnapshot, Snowfall, Temperature

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

    current_temp = _extract_float(tree.css_first("section#temperatures .current-temp").text())
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

    snowfall = Snowfall(
        last_12h=snowfall_values.get("12h"),
        last_24h=snowfall_values.get("24h"),
        last_7d=snowfall_values.get("7d"),
    )
    temperature = Temperature(current=current_temp, low=low_temp, high=high_temp)

    return ConditionSnapshot(
        resort_id=RESORT_ID,
        fetched_at=datetime.now(timezone.utc),
        snowfall=snowfall,
        temperature=temperature,
        wind_speed_mph=wind_speed,
        wind_direction=wind_direction,
        base_depth_in=base_depth,
        lifts_open=lifts_open,
        lifts_total=lifts_total,
        lift_status=lift_status,
        raw_source=REPORT_URL,
    )

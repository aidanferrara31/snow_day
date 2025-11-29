from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict

from selectolax.parser import HTMLParser

from ..models import ConditionSnapshot, Snowfall, Temperature

RESORT_ID = "summit_valley"
REPORT_URL = "https://example.com/summit-valley/conditions"


def _extract_numeric(text: str) -> float:
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not match:
        raise ValueError(f"No numeric value in '{text}'")
    return float(match.group(1))


def parse_conditions(html: str) -> ConditionSnapshot:
    tree = HTMLParser(html)

    wind_speed = None
    wind_direction = None
    wind_node = tree.css_first(".conditions .wind")
    if wind_node:
        wind_text = wind_node.text()
        match = re.search(r"(?P<direction>[A-Z]{1,3})\s+at\s+(?P<speed>\d+(?:\.\d+)?)", wind_text, re.IGNORECASE)
        if match:
            wind_speed = float(match.group("speed"))
            wind_direction = match.group("direction")

    base_depth = None
    base_node = tree.css_first(".conditions .base")
    if base_node:
        base_depth = _extract_numeric(base_node.text())

    snowfall = Snowfall(
        last_12h=_extract_numeric(tree.css_first(".conditions .snowfall .h12").text()),
        last_24h=_extract_numeric(tree.css_first(".conditions .snowfall .h24").text()),
        last_7d=_extract_numeric(tree.css_first(".conditions .snowfall .d7").text()),
    )

    temps = {row.css_first("th").text(strip=True).lower(): _extract_numeric(row.css_first("td").text()) for row in tree.css("table.temps tr")}
    temperature = Temperature(
        current=temps.get("current"),
        low=temps.get("low"),
        high=temps.get("high"),
    )

    lift_status: Dict[str, str] = {}
    for row in tree.css("table.lifts tr"):
        name = row.attributes.get("data-name", row.text(strip=True))
        status = row.attributes.get("data-status", row.text(strip=True))
        lift_status[name] = status.lower()

    lifts_open = sum(1 for status in lift_status.values() if status == "open")
    lifts_total = len(lift_status)

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

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, Mapping, MutableMapping

from selectolax.parser import HTMLParser

from ..models import ConditionSnapshot
from ..normalization import DEFAULT_NORMALIZER

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


def _extract_numeric(text: str) -> float:
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    if not match:
        raise ValueError(f"No numeric value in '{text}'")
    return float(match.group(1))


def parse_conditions(html: str, *, selectors: Mapping[str, str] | None = None) -> ConditionSnapshot:
    active_selectors: Dict[str, str] = {**DEFAULT_SELECTORS, **(selectors or {})}
    tree = HTMLParser(html)

    wind_speed = None
    wind_direction = None
    wind_selector = active_selectors.get("wind")
    if wind_selector:
        wind_node = tree.css_first(wind_selector)
        if wind_node:
            wind_text = wind_node.text()
            match = re.search(r"(?P<direction>[A-Z]{1,3})\s+at\s+(?P<speed>\d+(?:\.\d+)?)", wind_text, re.IGNORECASE)
            if match:
                wind_speed = float(match.group("speed"))
                wind_direction = match.group("direction")

    base_depth = None
    base_selector = active_selectors.get("base")
    if base_selector:
        base_node = tree.css_first(base_selector)
        if base_node:
            base_depth = _extract_numeric(base_node.text())

    snowfall = {
        "12h": _extract_numeric(tree.css_first(active_selectors["snowfall_12h"]).text()),
        "24h": _extract_numeric(tree.css_first(active_selectors["snowfall_24h"]).text()),
        "7d": _extract_numeric(tree.css_first(active_selectors["snowfall_7d"]).text()),
    }

    temps = {
        row.css_first("th").text(strip=True).lower(): _extract_numeric(row.css_first("td").text())
        for row in tree.css(active_selectors["temps_table"])
    }

    lift_status: Dict[str, str] = {}
    for row in tree.css(active_selectors["lifts_table"]):
        name = row.attributes.get(active_selectors.get("lift_name_attr", ""), row.text(strip=True))
        status = row.attributes.get(active_selectors.get("lift_status_attr", ""), row.text(strip=True))
        lift_status[name] = status.lower()

    lifts_open = sum(1 for status in lift_status.values() if status == "open")
    lifts_total = len(lift_status)

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

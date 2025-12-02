"""Scraper for Cannon Mountain, NH.

Source: https://www.cannonmt.com/mountain-report
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional, Tuple

from bs4 import BeautifulSoup

from ..models import ConditionSnapshot
from ..normalization import DEFAULT_NORMALIZER

RESORT_ID = "cannon_mountain"
DEFAULT_REPORT_URL = "https://www.cannonmt.com/mountain-report"


def _extract_count(label: str, text: str) -> Tuple[Optional[int], Optional[int]]:
    pattern = rf"{label}\s*(\d+)\s*(?:of|/)\s*(\d+)"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))

    match = re.search(rf"(\d+)\s*(?:of|/)\s*(\d+)\s*{label}", text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))

    match = re.search(rf"{label}\s*(\d+)", text, re.IGNORECASE)
    if match:
        return int(match.group(1)), None

    return None, None


def _detect_operational_status(text: str, trails_open: Optional[int], lifts_open: Optional[int]) -> Optional[bool]:
    lowered = text.lower()
    if "mountain ops status" in lowered and "open" in lowered:
        return True
    if "closed for the season" in lowered or "temporarily closed" in lowered:
        return False
    if trails_open and trails_open > 0:
        return True
    if lifts_open and lifts_open > 0:
        return True
    return None


def parse_conditions(html: str, **kwargs) -> ConditionSnapshot:
    """Parse Cannon Mountain snow report HTML into a ConditionSnapshot."""
    # Strip HTML tags and clean up the text for regex matching
    full_text = re.sub(r'<[^>]+>', ' ', html)
    full_text = re.sub(r'<!--.*?-->', '', full_text)
    full_text = re.sub(r'\s+', ' ', full_text)

    # Initialize all values
    base_depth = None
    snowfall_24h = None
    snowfall_48h = None
    temp_low = None
    temp_high = None
    wind_speed = None
    precip_type = None
    lifts_open = None
    lifts_total = None
    trails_open = None
    trails_total = None

    # Find temperatures - pattern: LOW XX° and HIGH XX°
    low_match = re.search(r'LOW\s*(\d+)\s*[°ºo]', full_text, re.IGNORECASE)
    high_match = re.search(r'HIGH\s*(\d+)\s*[°ºo]', full_text, re.IGNORECASE)
    if low_match:
        temp_low = float(low_match.group(1))
    if high_match:
        temp_high = float(high_match.group(1))

    # Find wind - pattern: BASE S/SW, 5-12 mph
    wind_match = re.search(r'BASE\s*([NSEW/]+)[,\s]*(\d+)-(\d+)\s*mph', full_text, re.IGNORECASE)
    if wind_match:
        low_wind = int(wind_match.group(2))
        high_wind = int(wind_match.group(3))
        wind_speed = (low_wind + high_wind) / 2

    # Find snowfall - pattern: 5" Last 48 Hours
    snow_match = re.search(r'(\d+)\s*["\u201d]\s*Last\s*48', full_text, re.IGNORECASE)
    if snow_match:
        snowfall_48h = float(snow_match.group(1))
        snowfall_24h = snowfall_48h / 2  # Estimate 24h as half of 48h

    # Find base depth - Snowfall to Date
    depth_match = re.search(r'SNOWFALL\s*TO\s*DATE[^0-9]*(\d+)', full_text, re.IGNORECASE)
    if depth_match:
        base_depth = float(depth_match.group(1))

    # Find surface conditions
    surface_match = re.search(r'PRIMARY\s*SURFACE\s*([A-Za-z\s]+?)(?:SECONDARY|$)', full_text, re.IGNORECASE)
    if surface_match:
        precip_type = surface_match.group(1).strip()
    else:
        # Fallback: look for common conditions
        conditions = ["Powder", "Packed Powder", "Machine Groomed", "Loose Granular", "Ice", "Hardpack"]
        for condition in conditions:
            if condition.lower() in full_text.lower():
                precip_type = condition
                break

    lifts_open, lifts_total = _extract_count("LIFTS OPEN", full_text)
    trails_open, trails_total = _extract_count("TRAILS OPEN", full_text)
    status = _detect_operational_status(full_text, trails_open, lifts_open)

    raw_metrics = {
        "wind_speed_mph": wind_speed,
        "wind_chill_f": None,
        "temp_low_f": temp_low,
        "temp_high_f": temp_high,
        "snowfall_last_12h_in": None,
        "snowfall_last_24h_in": snowfall_24h,
        "snowfall_last_7d_in": None,
        "base_depth_in": base_depth,
        "precip_type": precip_type,
        "lifts_open": lifts_open,
        "lifts_total": lifts_total,
        "trails_open": trails_open,
        "trails_total": trails_total,
        "is_operational": status,
    }

    return DEFAULT_NORMALIZER.normalize(
        RESORT_ID,
        raw_metrics,
        timestamp=datetime.now(timezone.utc),
    )

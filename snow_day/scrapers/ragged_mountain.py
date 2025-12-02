"""Scraper for Ragged Mountain, NH via their direct website.

Source: https://www.raggedmountainresort.com/mountain-report-cams/
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from ..models import ConditionSnapshot
from ..normalization import DEFAULT_NORMALIZER

RESORT_ID = "ragged_mountain"
DEFAULT_REPORT_URL = "https://www.raggedmountainresort.com/mountain-report-cams/"


def parse_conditions(html: str, **kwargs) -> ConditionSnapshot:
    """Parse Ragged Mountain snow report HTML into a ConditionSnapshot."""
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

    # Extract snowfall - Ragged uses format: <h6>Last 24 hrs.</h6> <h3>1"</h3>
    # Pattern: Last 24 hrs. ... number"
    snow_24h_match = re.search(r'Last 24 hrs\.\s*(\d+(?:\.\d+)?)\s*["\u201d]', full_text, re.IGNORECASE)
    if snow_24h_match:
        snowfall_24h = float(snow_24h_match.group(1))

    # Extract 48hr snowfall
    snow_48h_match = re.search(r'Last 48 hrs\.\s*(\d+(?:\.\d+)?)\s*["\u201d]', full_text, re.IGNORECASE)
    if snow_48h_match:
        snowfall_48h = float(snow_48h_match.group(1))

    # Extract Current Base
    base_match = re.search(r'Current Base\s*(\d+(?:\.\d+)?)\s*["\u201d]', full_text, re.IGNORECASE)
    if base_match:
        base_depth = float(base_match.group(1))

    # Extract temperature - format: 23.4° F or H: 23.6° F or L: 19.4° F
    temp_high_match = re.search(r"H:\s*(?:<[^>]+>)?\s*(\d+(?:\.\d+)?)\s*°\s*F", full_text, re.IGNORECASE)
    if temp_high_match:
        temp_high = float(temp_high_match.group(1))
    
    temp_low_match = re.search(r"L:\s*(?:<[^>]+>)?\s*(\d+(?:\.\d+)?)\s*°\s*F", full_text, re.IGNORECASE)
    if temp_low_match:
        temp_low = float(temp_low_match.group(1))

    # Also try to get temps from the original HTML structure: <span>H: <span class="temprature">23.6° F</span></span>
    if temp_high is None:
        temp_high_html_match = re.search(r'H:\s*<span[^>]*>\s*(\d+(?:\.\d+)?)\s*°\s*F', html, re.IGNORECASE)
        if temp_high_html_match:
            temp_high = float(temp_high_html_match.group(1))
    
    if temp_low is None:
        temp_low_html_match = re.search(r'L:\s*<span[^>]*>\s*(\d+(?:\.\d+)?)\s*°\s*F', html, re.IGNORECASE)
        if temp_low_html_match:
            temp_low = float(temp_low_html_match.group(1))

    # Extract wind speed - format: Wind 0.3 mph or Wind <span class="content">0.3 mph</span>
    wind_match = re.search(r"Wind\s*(?:<[^>]+>)?\s*(\d+(?:\.\d+)?)\s*mph", full_text, re.IGNORECASE)
    if wind_match:
        wind_speed = float(wind_match.group(1))
    
    # Also try from original HTML
    if wind_speed is None:
        wind_html_match = re.search(r'Wind\s*<span[^>]*>\s*(\d+(?:\.\d+)?)\s*mph', html, re.IGNORECASE)
        if wind_html_match:
            wind_speed = float(wind_html_match.group(1))

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
    }

    return DEFAULT_NORMALIZER.normalize(
        RESORT_ID,
        raw_metrics,
        timestamp=datetime.now(timezone.utc),
    )

"""Scraper for Pat's Peak, NH via OnTheSnow.

Source: https://www.onthesnow.com/new-hampshire/pats-peak/skireport
Note: Pat's Peak doesn't always report conditions to OnTheSnow.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import ConditionSnapshot
from ..normalization import DEFAULT_NORMALIZER
from .base import parse_onthesnow

RESORT_ID = "pats_peak"
DEFAULT_REPORT_URL = "https://www.onthesnow.com/new-hampshire/pats-peak/skireport"


def parse_conditions(html: str, **kwargs) -> ConditionSnapshot:
    """Parse OnTheSnow Pat's Peak snow report HTML into a ConditionSnapshot."""
    raw_metrics = parse_onthesnow(html)

    return DEFAULT_NORMALIZER.normalize(
        RESORT_ID,
        raw_metrics,
        timestamp=datetime.now(timezone.utc),
    )

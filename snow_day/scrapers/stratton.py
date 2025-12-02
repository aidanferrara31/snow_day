"""Scraper for Stratton Mountain, VT via OnTheSnow.

Source: https://www.onthesnow.com/vermont/stratton-mountain/skireport
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import ConditionSnapshot
from ..normalization import DEFAULT_NORMALIZER
from .base import parse_onthesnow

RESORT_ID = "stratton"
DEFAULT_REPORT_URL = "https://www.onthesnow.com/vermont/stratton-mountain/skireport"


def parse_conditions(html: str, **kwargs) -> ConditionSnapshot:
    """Parse OnTheSnow Stratton snow report HTML into a ConditionSnapshot."""
    raw_metrics = parse_onthesnow(html)

    return DEFAULT_NORMALIZER.normalize(
        RESORT_ID,
        raw_metrics,
        timestamp=datetime.now(timezone.utc),
    )

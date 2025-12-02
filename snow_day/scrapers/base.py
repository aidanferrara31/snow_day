"""Base utilities for ski resort scrapers using BeautifulSoup."""
from __future__ import annotations

import re
from typing import Optional, Tuple

from bs4 import BeautifulSoup, Tag


def create_soup(html: str) -> BeautifulSoup:
    """Create a BeautifulSoup parser from HTML content."""
    return BeautifulSoup(html, "lxml")


def extract_numeric(text: str) -> Optional[float]:
    """Extract first numeric value from text."""
    if not text:
        return None
    match = re.search(r"(-?\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def parse_wind(text: str) -> Tuple[Optional[float], Optional[str]]:
    """Parse wind speed and direction from various text formats.
    
    Handles formats like:
    - "NW, 5-12 mph"
    - "W/NW, 17-30 mph"  
    - "NW 15 mph"
    - "5-12 mph NW"
    """
    if not text:
        return None, None
    
    # Try direction first pattern: "NW, 5-12 mph"
    match = re.search(r"([NSEW/]{1,4})[,]?\s*(\d+)(?:\s*-\s*(\d+))?\s*mph", text, re.IGNORECASE)
    if match:
        direction = match.group(1).upper().replace("/", "")
        low = int(match.group(2))
        high = int(match.group(3)) if match.group(3) else low
        speed = (low + high) / 2
        return speed, direction
    
    # Try mph then direction: "5-12 mph NW"
    match = re.search(r"(\d+)(?:\s*-\s*(\d+))?\s*mph\s*([NSEW]{1,2})", text, re.IGNORECASE)
    if match:
        low = int(match.group(1))
        high = int(match.group(2)) if match.group(2) else low
        direction = match.group(3).upper()
        speed = (low + high) / 2
        return speed, direction
    
    # Try just mph without direction: "5-12 mph"
    match = re.search(r"(\d+)(?:\s*-\s*(\d+))?\s*mph", text, re.IGNORECASE)
    if match:
        low = int(match.group(1))
        high = int(match.group(2)) if match.group(2) else low
        speed = (low + high) / 2
        return speed, None
    
    return None, None


def parse_temperature(text: str) -> Tuple[Optional[float], Optional[float]]:
    """Parse low and high temperatures from text.
    
    Returns (low, high) tuple.
    """
    if not text:
        return None, None
    
    temp_low = None
    temp_high = None
    
    # Try "LOW XX" and "HIGH XX" patterns
    low_match = re.search(r"LOW\s*:?\s*(-?\d+)", text, re.IGNORECASE)
    high_match = re.search(r"HIGH\s*:?\s*(-?\d+)", text, re.IGNORECASE)
    
    if low_match:
        temp_low = float(low_match.group(1))
    if high_match:
        temp_high = float(high_match.group(1))
    
    # If not found, try finding degree patterns
    if temp_low is None or temp_high is None:
        temps = re.findall(r"(-?\d+)\s*[°ºF]", text)
        if len(temps) >= 2:
            temp_values = [float(t) for t in temps]
            if temp_low is None:
                temp_low = min(temp_values)
            if temp_high is None:
                temp_high = max(temp_values)
        elif len(temps) == 1:
            if temp_high is None:
                temp_high = float(temps[0])
    
    return temp_low, temp_high


def find_text_by_label(soup: BeautifulSoup, label: str, search_scope: Tag = None) -> Optional[str]:
    """Find text value associated with a label.
    
    Searches for elements containing the label text and returns the 
    value in an adjacent element.
    """
    search_in = search_scope or soup
    
    # Find elements containing the label
    for element in search_in.find_all(string=re.compile(label, re.IGNORECASE)):
        parent = element.find_parent()
        if parent:
            # Try next sibling
            next_sib = parent.find_next_sibling()
            if next_sib:
                return next_sib.get_text(strip=True)
            # Try parent's next sibling
            parent_next = parent.parent.find_next_sibling() if parent.parent else None
            if parent_next:
                return parent_next.get_text(strip=True)
    
    return None


def find_surface_condition(soup: BeautifulSoup) -> Optional[str]:
    """Find snow surface condition from page text."""
    full_text = soup.get_text()
    surface_patterns = [
        "Machine Groomed",
        "Packed Powder", 
        "Loose Granular",
        "Powder",
        "Hardpack",
        "Frozen Granular",
        "Variable",
        "Spring Conditions",
        "Ice",
    ]
    
    for pattern in surface_patterns:
        if pattern.lower() in full_text.lower():
            return pattern
    
    return None


def parse_lifts_fraction(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse lift status like '5 of 12' or '5/12' into (open, total)."""
    if not text:
        return None, None
    
    match = re.search(r"(\d+)\s*(?:of|/)\s*(\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    
    # Just a number - assume it's open lifts
    single = extract_numeric(text)
    if single:
        return int(single), None
    
    return None, None


def _detect_onthesnow_status(text: str) -> Optional[bool]:
    """Infer whether a resort is operating based on common OnTheSnow phrases."""
    lowered = text.lower()
    status_match = re.search(r"status\s*:?\s*(open|closed)", lowered)
    if status_match:
        return status_match.group(1) == "open"

    closed_markers = [
        "projected opening",
        "resort closed",
        "closed for the season",
        "temporarily closed",
        "season opening",
    ]
    if any(marker in lowered for marker in closed_markers):
        return False
    return None


def _extract_open_counts(text: str, keywords: Tuple[str, ...]) -> Tuple[Optional[int], Optional[int]]:
    """Extract open/total counts for lifts or trails."""

    def _pattern(keyword: str) -> str:
        return rf"{keyword}\s*(\d+)\s*(?:of|/)\s*(\d+)"

    for keyword in keywords:
        match = re.search(_pattern(keyword), text, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))

    # Handle reversed order: "5 of 12 lifts open"
    for keyword in keywords:
        match = re.search(rf"(\d+)\s*(?:of|/)\s*(\d+)\s*{keyword}", text, re.IGNORECASE)
        if match:
            return int(match.group(1)), int(match.group(2))

    # Handle single value "Lifts Open 5"
    for keyword in keywords:
        match = re.search(rf"{keyword}\s*(\d+)", text, re.IGNORECASE)
        if match:
            return int(match.group(1)), None

    return None, None


def parse_onthesnow(html: str) -> dict:
    """Parse OnTheSnow.com ski report HTML into a metrics dictionary.
    
    OnTheSnow provides standardized ski condition data for many resorts.
    Returns a dict with raw metrics ready for the normalizer.
    """
    soup = create_soup(html)
    text = soup.get_text(' ', strip=True)
    
    base_depth = None
    snowfall_24h = None
    precip_type = None
    
    # Extract base depth: "Base 10" Variable Conditions"
    base_match = re.search(r'Base\s*(\d+)["\u2033″]', text)
    if base_match:
        base_depth = float(base_match.group(1))
    
    # Extract 24h snowfall from the recent snowfall row
    # Pattern: "24h 0"" or individual day amounts
    snow_24h_match = re.search(r'24h\s*(\d+)["\u2033″]', text)
    if snow_24h_match:
        snowfall_24h = float(snow_24h_match.group(1))
    
    # Extract surface conditions - look after "Base XX" for conditions
    surface_match = re.search(r'Base\s*\d+["\u2033″]\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)\s*Conditions', text)
    if surface_match:
        precip_type = surface_match.group(1).strip()
    else:
        # Fallback to finding common condition keywords
        precip_type = find_surface_condition(soup)

    lifts_open, lifts_total = _extract_open_counts(text, ("lifts open", "open lifts", "lifts running"))
    trails_open, trails_total = _extract_open_counts(text, ("trails open", "open trails", "runs open", "open runs"))

    # Prioritize trails/lifts data over text-based status detection
    # If we have open trails or lifts, the resort is definitely open
    if trails_open and trails_open > 0:
        status = True
    elif lifts_open and lifts_open > 0:
        status = True
    else:
        # Only use text-based detection if we don't have trail/lift data
        status = _detect_onthesnow_status(text)
    
    return {
        "wind_speed_mph": None,  # OnTheSnow doesn't typically show wind
        "wind_chill_f": None,
        "temp_low_f": None,
        "temp_high_f": None,
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


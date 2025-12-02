from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from snow_day.http_client import DEFAULT_USER_AGENT

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass
class WeatherObservation:
    """Represents supplemental weather details retrieved from Open-Meteo."""

    temperature_f: Optional[float] = None
    wind_speed_mph: Optional[float] = None


def fetch_current_weather(
    latitude: float,
    longitude: float,
    *,
    client: Optional[httpx.Client] = None,
) -> WeatherObservation:
    """Fetch near real-time weather for the given coordinates.

    Uses Open-Meteo's free API which does not require an API key and supports
    direct unit selection. Falls back gracefully when either metric is absent.
    """

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,wind_speed_10m",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
    }

    if client is not None:
        response = client.get(OPEN_METEO_URL, params=params)
    else:
        response = httpx.get(
            OPEN_METEO_URL,
            params=params,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            timeout=10.0,
        )

    response.raise_for_status()
    data = response.json()
    current = data.get("current") or {}

    return WeatherObservation(
        temperature_f=current.get("temperature_2m"),
        wind_speed_mph=current.get("wind_speed_10m"),
    )


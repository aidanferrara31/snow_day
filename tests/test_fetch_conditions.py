from __future__ import annotations

from pathlib import Path
from typing import Callable

import httpx
import pytest

from snow_day.cache import LastModifiedCache
from snow_day.scrapers import fetch_conditions
from snow_day.scrapers import alpine_peak, summit_valley

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text()


def _make_mock_transport(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_alpine_peak_parsing() -> None:
    html = _fixture_text("alpine_peak.html")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"Last-Modified": "Wed, 01 Jan 2024 00:00:00 GMT"})

    client = httpx.Client(transport=_make_mock_transport(handler))
    cache = LastModifiedCache()

    snapshot = fetch_conditions(alpine_peak.RESORT_ID, client=client, cache=cache)

    assert snapshot.snowfall.last_12h == 3
    assert snapshot.snowfall.last_24h == 5
    assert snapshot.snowfall.last_7d == 18
    assert snapshot.temperature.current == 28
    assert snapshot.wind_speed_mph == 12
    assert snapshot.wind_direction == "NW"
    assert snapshot.base_depth_in == 60
    assert snapshot.lifts_open == 7
    assert snapshot.lifts_total == 10
    assert snapshot.lift_status["Summit Chair"] == "open"
    assert snapshot.lift_status["Glades Quad"] == "hold"


def test_summit_valley_parsing() -> None:
    html = _fixture_text("summit_valley.html")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = httpx.Client(transport=_make_mock_transport(handler))
    snapshot = fetch_conditions(summit_valley.RESORT_ID, client=client, cache=LastModifiedCache())

    assert snapshot.snowfall.last_12h == 1
    assert snapshot.snowfall.last_24h == 2
    assert snapshot.snowfall.last_7d == 12
    assert snapshot.temperature.current == 30
    assert snapshot.temperature.high == 34
    assert snapshot.temperature.low == 26
    assert snapshot.wind_speed_mph == 8
    assert snapshot.wind_direction == "NW"
    assert snapshot.base_depth_in == 72
    assert snapshot.lifts_open == 1
    assert snapshot.lifts_total == 2
    assert snapshot.lift_status["Gondola"] == "open"
    assert snapshot.lift_status["Backside"] == "closed"


def test_last_modified_caching_uses_snapshot() -> None:
    html = _fixture_text("alpine_peak.html")
    last_modified = "Wed, 01 Jan 2024 00:00:00 GMT"
    call_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["count"] += 1
        if call_count["count"] == 1:
            return httpx.Response(200, text=html, headers={"Last-Modified": last_modified})
        assert request.headers.get("If-Modified-Since") == last_modified
        return httpx.Response(304, headers={"Last-Modified": last_modified})

    client = httpx.Client(transport=_make_mock_transport(handler))
    cache = LastModifiedCache()

    first_snapshot = fetch_conditions(alpine_peak.RESORT_ID, client=client, cache=cache)
    second_snapshot = fetch_conditions(alpine_peak.RESORT_ID, client=client, cache=cache)

    assert call_count["count"] == 2
    assert second_snapshot is first_snapshot


def test_unknown_resort_error() -> None:
    with pytest.raises(KeyError):
        fetch_conditions("missing", client=httpx.Client(transport=_make_mock_transport(lambda _: httpx.Response(404))))

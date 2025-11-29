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

    assert snapshot.snowfall_12h == 3
    assert snapshot.snowfall_24h == 5
    assert snapshot.snowfall_7d == 18
    assert snapshot.temp_min == 22
    assert snapshot.temp_max == 32
    assert snapshot.wind_speed == 12
    assert snapshot.wind_chill is None
    assert snapshot.base_depth == 60
    assert snapshot.precip_type is None
    assert snapshot.timestamp.tzinfo is not None


def test_summit_valley_parsing() -> None:
    html = _fixture_text("summit_valley.html")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = httpx.Client(transport=_make_mock_transport(handler))
    snapshot = fetch_conditions(summit_valley.RESORT_ID, client=client, cache=LastModifiedCache())

    assert snapshot.snowfall_12h == 1
    assert snapshot.snowfall_24h == 2
    assert snapshot.snowfall_7d == 12
    assert snapshot.temp_min == 26
    assert snapshot.temp_max == 34
    assert snapshot.wind_speed == 8
    assert snapshot.wind_chill is None
    assert snapshot.base_depth == 72


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

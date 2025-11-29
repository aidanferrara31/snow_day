from datetime import datetime, timezone

import pytest

from snow_day.normalization import ConditionNormalizer, FieldMapping


def test_normalizer_converts_units_and_fields():
    normalizer = ConditionNormalizer(
        mappings={
            "metric_hill": {
                "wind_speed": FieldMapping("wind_kph", converter=ConditionNormalizer._kph_to_mph),
                "temp_min": FieldMapping("temp_low_c", converter=ConditionNormalizer._c_to_f),
                "temp_max": FieldMapping("temp_high_c", converter=ConditionNormalizer._c_to_f),
                "snowfall_24h": FieldMapping("snow_cm", converter=ConditionNormalizer._cm_to_inches),
                "base_depth": FieldMapping("base_cm", converter=ConditionNormalizer._cm_to_inches),
                "precip_type": FieldMapping("precip"),
            }
        }
    )

    timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    snapshot = normalizer.normalize(
        "metric_hill",
        {
            "wind_kph": 20,
            "temp_low_c": -5,
            "temp_high_c": 2,
            "snow_cm": 30,
            "base_cm": 120,
            "precip": "snow",
        },
        timestamp=timestamp,
    )

    assert snapshot.wind_speed == pytest.approx(12.42742)
    assert snapshot.temp_min == pytest.approx(23.0)
    assert snapshot.temp_max == pytest.approx(35.6)
    assert snapshot.snowfall_24h == pytest.approx(11.81103)
    assert snapshot.base_depth == pytest.approx(47.24412)
    assert snapshot.precip_type == "snow"
    assert snapshot.timestamp == timestamp

from datetime import datetime, timezone

import os

from snow_day.models import ConditionSnapshot
from snow_day.services.scoring import ScoringConfig, score_snapshot


def make_snapshot(**kwargs):
    return ConditionSnapshot(
        resort_id="test",
        timestamp=datetime.now(timezone.utc),
        **kwargs,
    )


def test_powder_and_icy_flags():
    previous = make_snapshot(precip_type="snow", snowfall_24h=4)
    current = make_snapshot(temp_min=10, temp_max=28, wind_speed=15, base_depth=30)

    result = score_snapshot(current, previous_snapshots=[previous])

    assert result.powder is True
    assert result.icy is True
    assert "Powder flag" in result.rationale
    assert "Icy flag" in result.rationale
    assert result.score < 100


def test_gust_penalty_and_fresh_snow_bonus():
    current = make_snapshot(
        snowfall_24h=6,
        wind_speed=40,
        base_depth=10,
        temp_min=25,
        temp_max=35,
    )

    result = score_snapshot(current)

    assert "Fresh snow" in result.rationale
    assert "Wind gust penalty" in result.rationale
    assert result.score > 0


def test_prior_day_rain_sets_icy_flag():
    previous = make_snapshot(precip_type="rain")
    current = make_snapshot(temp_min=33, temp_max=40, base_depth=25)

    result = score_snapshot(current, previous_snapshots=[previous])

    assert result.icy is True
    assert "Icy flag" in result.rationale


def test_config_from_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("SNOWDAY_SCORING_BASE_SCORE", "5")
    monkeypatch.setenv("SNOWDAY_SCORING_ICY_PENALTY", "5")

    config = ScoringConfig.from_sources(env=os.environ)
    current = make_snapshot(temp_min=20, temp_max=30, base_depth=0)

    result = score_snapshot(current, config=config)

    assert config.base_score == 5
    assert config.icy_penalty == 5
    expected = (
        config.base_score
        + (config.base_depth_floor * config.base_depth_weight)
        - config.icy_penalty
    )
    assert result.score == expected

def test_base_depth_floor_is_used():
    config = ScoringConfig(base_depth_floor=20, base_depth_weight=1)
    current = make_snapshot(base_depth=5, temp_max=40)

    result = score_snapshot(current, config=config)

    assert "floored" in result.rationale
    assert result.score >= config.base_score + config.base_depth_floor

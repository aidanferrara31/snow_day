from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple

from snow_day.config import app_config
from snow_day.models import ConditionSnapshot


@dataclass
class ScoringConfig:
    """Configuration for the scoring algorithm.

    Values can be overridden via a config mapping, a JSON config file, or
    environment variables prefixed with ``SNOWDAY_SCORING_``.
    """

    base_score: float = 50.0
    max_score: float = 100.0
    min_score: float = 0.0

    base_depth_floor: float = 18.0
    base_depth_weight: float = 0.5

    gust_penalty_threshold: float = 25.0
    gust_penalty_per_mph: float = 0.75

    fresh_snow_bonus_per_inch: float = 2.0
    powder_bonus: float = 12.0
    icy_penalty: float = 15.0

    @classmethod
    def from_sources(
        cls,
        *,
        config_path: Optional[str] = None,
        env: Mapping[str, str] | None = None,
        config_data: Mapping[str, float] | None = None,
    ) -> "ScoringConfig":
        """Load configuration from defaults, file overrides, and environment.

        ``config_path`` should point to a JSON file where keys mirror the
        dataclass fields. Environment variables use uppercase names prefixed
        with ``SNOWDAY_SCORING_`` (e.g., ``SNOWDAY_SCORING_ICY_PENALTY``).
        ``config_data`` allows callers to inject values loaded from YAML.
        """

        env = dict(env or os.environ)
        data: Dict[str, float] = {}

        if config_data:
            data.update({k: float(v) for k, v in config_data.items() if v is not None})

        if config_path:
            path = Path(config_path)
            if path.exists():
                loaded = json.loads(path.read_text())
                data.update({k: float(v) for k, v in loaded.items() if v is not None})

        prefix = "SNOWDAY_SCORING_"
        for key, value in env.items():
            if key.startswith(prefix):
                field = key.removeprefix(prefix).lower()
                if hasattr(cls, field):
                    try:
                        data[field] = float(value)
                    except ValueError:
                        continue

        return cls(**data)


@dataclass
class ScoreResult:
    score: float
    rationale: str
    powder: bool = False
    icy: bool = False


def _apply_base_depth(snapshot: ConditionSnapshot, config: ScoringConfig) -> Tuple[float, str]:
    depth = snapshot.base_depth or 0.0
    adjusted_depth = max(depth, config.base_depth_floor)
    contribution = adjusted_depth * config.base_depth_weight
    rationale = f"Base depth used: {adjusted_depth:.1f}in"
    if depth < config.base_depth_floor:
        rationale += f" (floored from {depth:.1f}in)"
    return contribution, rationale


def _fresh_snow_bonus(snapshot: ConditionSnapshot, config: ScoringConfig) -> Tuple[float, str]:
    fresh_inches = snapshot.snowfall_24h
    if fresh_inches is None:
        fresh_inches = snapshot.snowfall_12h or 0.0
    bonus = (fresh_inches or 0.0) * config.fresh_snow_bonus_per_inch
    return bonus, f"Fresh snow: {fresh_inches or 0.0:.1f}in"


def _gust_penalty(snapshot: ConditionSnapshot, config: ScoringConfig) -> Tuple[float, str]:
    wind = snapshot.wind_speed or 0.0
    if wind <= config.gust_penalty_threshold:
        return 0.0, "Winds below gust threshold"
    overage = wind - config.gust_penalty_threshold
    penalty = overage * config.gust_penalty_per_mph
    return -penalty, f"Wind gust penalty from {wind:.1f}mph"


def _temperature_icy(snapshot: ConditionSnapshot) -> bool:
    if snapshot.temp_max is None:
        return False
    return snapshot.temp_max <= 32.0


def _powder_flag(previous: Optional[ConditionSnapshot]) -> bool:
    if not previous:
        return False
    if previous.precip_type:
        return previous.precip_type.lower() == "snow"
    return (previous.snowfall_24h or 0) > 0 or (previous.snowfall_12h or 0) > 0


def _icy_flag(previous: Optional[ConditionSnapshot], current: ConditionSnapshot) -> bool:
    if previous and previous.precip_type:
        if previous.precip_type.lower() == "rain":
            return True
    return _temperature_icy(current)


def score_snapshot(
    current: ConditionSnapshot,
    *,
    previous_snapshots: Optional[Iterable[ConditionSnapshot]] = None,
    config: Optional[ScoringConfig] = None,
) -> ScoreResult:
    """Score the current snapshot and return the numeric score and rationale.

    The most recent entry in ``previous_snapshots`` is treated as the prior-day
    reading for powder/icy determination.
    """

    config = config or ScoringConfig.from_sources(config_data=app_config.scoring)
    previous_snapshot = None
    if previous_snapshots:
        previous_snapshot = list(previous_snapshots)[-1]

    score = config.base_score
    rationales = []

    base_contribution, base_note = _apply_base_depth(current, config)
    score += base_contribution
    rationales.append(base_note)

    snow_bonus, snow_note = _fresh_snow_bonus(current, config)
    score += snow_bonus
    rationales.append(snow_note)

    powder = _powder_flag(previous_snapshot)
    if powder:
        score += config.powder_bonus
        rationales.append("Powder flag applied")

    icy = _icy_flag(previous_snapshot, current)
    if icy:
        score -= config.icy_penalty
        rationales.append("Icy flag applied")

    wind_penalty, wind_note = _gust_penalty(current, config)
    score += wind_penalty
    rationales.append(wind_note)

    clamped_score = max(config.min_score, min(score, config.max_score))
    rationales.append(f"Clamped to range {config.min_score}-{config.max_score}")

    return ScoreResult(score=clamped_score, rationale="; ".join(rationales), powder=powder, icy=icy)

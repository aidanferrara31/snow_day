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
    base_depth_bonus_per_inch: float = 0.3  # Bonus for each inch above floor

    wind_ideal: float = 0.0  # Ideal wind speed
    wind_penalty_per_mph: float = 0.5  # Penalty for each mph above ideal

    temp_ideal_min: float = 32.0  # Ideal temperature range
    temp_ideal_max: float = 38.0
    temp_penalty_per_degree: float = 0.4  # Penalty for each degree outside ideal range

    trails_open_bonus_per_percent: float = 0.2  # Bonus per % of trails open
    lifts_open_bonus_per_percent: float = 0.15  # Bonus per % of lifts open

    fresh_snow_bonus_per_inch: float = 2.0
    powder_bonus: float = 12.0
    icy_penalty: float = 15.0
    closed_resort_penalty: float = 1000.0  # Large penalty to ensure 0 score
    unknown_status_penalty: float = 10.0
    missing_metric_penalty: float = 5.0
    low_base_penalty_per_inch: float = 0.75

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

        # Backward compatibility: map old field names to new ones
        field_mapping = {
            "gust_penalty_threshold": None,  # Removed, no longer needed
            "gust_penalty_per_mph": "wind_penalty_per_mph",
        }
        for old_field, new_field in field_mapping.items():
            if old_field in data:
                if new_field:
                    # Map old field to new field
                    if new_field not in data:
                        data[new_field] = data[old_field]
                    del data[old_field]
                else:
                    # Remove deprecated field
                    del data[old_field]

        return cls(**data)


@dataclass
class ScoreResult:
    score: float
    rationale: str
    powder: bool = False
    icy: bool = False


def _apply_base_depth(snapshot: ConditionSnapshot, config: ScoringConfig) -> Tuple[float, str, float, Optional[str]]:
    """Returns contribution, rationale, penalty, penalty rationale."""

    depth = snapshot.base_depth
    if depth is None:
        adjusted_depth = config.base_depth_floor
        rationale = f"Base depth missing; assuming {adjusted_depth:.1f}in target"
        penalty = 0.0
        penalty_note = None
    else:
        adjusted_depth = depth
        rationale = f"Base depth: {depth:.1f}in"
        penalty = 0.0
        penalty_note = None
        
        if depth < config.base_depth_floor:
            shortfall = config.base_depth_floor - depth
            penalty = shortfall * config.low_base_penalty_per_inch
            penalty_note = f"Lost {penalty:.1f} pts because base is below the {config.base_depth_floor:.0f}\" target"

    # Base contribution + bonus for depth above ideal
    base_contribution = adjusted_depth * config.base_depth_weight
    if depth and depth > config.base_depth_floor:
        excess = depth - config.base_depth_floor
        bonus = excess * config.base_depth_bonus_per_inch
        base_contribution += bonus
    
    return base_contribution, rationale, penalty, penalty_note


def _fresh_snow_bonus(snapshot: ConditionSnapshot, config: ScoringConfig) -> Tuple[float, str]:
    fresh_inches = snapshot.snowfall_24h
    if fresh_inches is None:
        fresh_inches = snapshot.snowfall_12h or 0.0
    resolved = fresh_inches if fresh_inches is not None else 0.0
    bonus = resolved * config.fresh_snow_bonus_per_inch
    return bonus, f"Fresh snow: {resolved:.1f}in"


def _wind_scoring(snapshot: ConditionSnapshot, config: ScoringConfig) -> Tuple[float, str]:
    """Lower wind = better score. Continuous penalty for wind above ideal."""
    wind = snapshot.wind_speed or 0.0
    if wind <= config.wind_ideal:
        return 0.0, f"Calm winds ({wind:.1f}mph)"
    overage = wind - config.wind_ideal
    penalty = overage * config.wind_penalty_per_mph
    return -penalty, f"Wind penalty: {wind:.1f}mph (ideal: {config.wind_ideal:.0f}mph)"


def _temperature_icy(snapshot: ConditionSnapshot) -> bool:
    if snapshot.temp_max is None:
        return False
    return snapshot.temp_max <= 32.0


def _temperature_scoring(snapshot: ConditionSnapshot, config: ScoringConfig) -> Tuple[float, str]:
    """Ideal temp is 32-38°F. Penalize outside this range."""
    if snapshot.temp_max is None or snapshot.temp_min is None:
        return 0.0, "Temperature data missing"
    
    # Use average temp for scoring
    avg_temp = (snapshot.temp_min + snapshot.temp_max) / 2.0
    
    if config.temp_ideal_min <= avg_temp <= config.temp_ideal_max:
        return 0.0, f"Ideal temps: {snapshot.temp_min:.0f}°-{snapshot.temp_max:.0f}°F"
    
    penalty = 0.0
    if avg_temp < config.temp_ideal_min:
        # Below 32°F = icy conditions
        shortfall = config.temp_ideal_min - avg_temp
        penalty = shortfall * config.temp_penalty_per_degree
        return -penalty, f"Cold temps ({snapshot.temp_min:.0f}°-{snapshot.temp_max:.0f}°F) - icy conditions"
    else:
        # Above 38°F = slushy conditions
        excess = avg_temp - config.temp_ideal_max
        penalty = excess * config.temp_penalty_per_degree
        return -penalty, f"Warm temps ({snapshot.temp_min:.0f}°-{snapshot.temp_max:.0f}°F) - slushy conditions"


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


def _missing_metrics_penalty(snapshot: ConditionSnapshot, config: ScoringConfig) -> Tuple[float, Optional[str]]:
    metrics = {
        "base depth": snapshot.base_depth,
        "24h snow": snapshot.snowfall_24h,
        "wind": snapshot.wind_speed,
        "temps": snapshot.temp_max,
    }
    missing = [label for label, value in metrics.items() if value is None]
    if not missing:
        return 0.0, None
    penalty = config.missing_metric_penalty * len(missing)
    return penalty, f"Missing data for {', '.join(missing)} (-{penalty:.1f} pts)"


def _operational_penalty(snapshot: ConditionSnapshot, config: ScoringConfig) -> Tuple[float, str]:
    """Return large penalty if closed to ensure 0 score."""
    status = snapshot.is_operational
    if status is True:
        return 0.0, "Reported open"
    if status is False:
        return config.closed_resort_penalty, "Closed - no score"
    return config.unknown_status_penalty, "Unknown operating status penalty applied"


def _trails_lifts_bonus(snapshot: ConditionSnapshot, config: ScoringConfig) -> Tuple[float, str]:
    """More trails/lifts open = better score."""
    bonuses = []
    total_bonus = 0.0
    
    if snapshot.trails_total and snapshot.trails_total > 0 and snapshot.trails_open is not None:
        trails_pct = (snapshot.trails_open / snapshot.trails_total) * 100
        bonus = trails_pct * config.trails_open_bonus_per_percent
        total_bonus += bonus
        bonuses.append(f"{trails_pct:.0f}% trails")
    
    if snapshot.lifts_total and snapshot.lifts_total > 0 and snapshot.lifts_open is not None:
        lifts_pct = (snapshot.lifts_open / snapshot.lifts_total) * 100
        bonus = lifts_pct * config.lifts_open_bonus_per_percent
        total_bonus += bonus
        bonuses.append(f"{lifts_pct:.0f}% lifts")
    
    if bonuses:
        return total_bonus, f"Open: {', '.join(bonuses)}"
    return 0.0, "No trail/lift data"


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

    base_contribution, base_note, base_penalty, penalty_note = _apply_base_depth(current, config)
    score += base_contribution
    rationales.append(base_note)
    if base_penalty:
        score -= base_penalty
        if penalty_note:
            rationales.append(penalty_note)

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

    # Check if closed first - if closed, return 0 score
    op_penalty, op_note = _operational_penalty(current, config)
    if current.is_operational is False:
        # Resort is closed - return 0 score
        return ScoreResult(score=0.0, rationale="Closed - no score", powder=powder, icy=icy)
    
    if op_penalty:
        score -= op_penalty
    rationales.append(op_note)

    # Wind scoring (lower is better)
    wind_penalty, wind_note = _wind_scoring(current, config)
    score += wind_penalty
    rationales.append(wind_note)

    # Temperature scoring (32-38°F ideal)
    temp_penalty, temp_note = _temperature_scoring(current, config)
    score += temp_penalty
    rationales.append(temp_note)

    # Trails/lifts bonus (more open = better)
    trails_lifts_bonus, trails_lifts_note = _trails_lifts_bonus(current, config)
    score += trails_lifts_bonus
    rationales.append(trails_lifts_note)

    missing_penalty, missing_note = _missing_metrics_penalty(current, config)
    if missing_penalty:
        score -= missing_penalty
        if missing_note:
            rationales.append(missing_note)

    clamped_score = max(config.min_score, min(score, config.max_score))
    rationales.append(f"Clamped to range {config.min_score}-{config.max_score}")

    return ScoreResult(score=clamped_score, rationale="; ".join(rationales), powder=powder, icy=icy)

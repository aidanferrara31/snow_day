from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional


@dataclass
class ConditionSnapshot:
    """Normalized snow condition metrics for a resort.

    All numeric values are normalized to imperial units (mph, °F, inches) so
    downstream consumers can rely on consistent measurements regardless of the
    source resort.
    """

    resort_id: str
    timestamp: datetime
    wind_speed: Optional[float] = None
    wind_chill: Optional[float] = None
    temp_min: Optional[float] = None
    temp_max: Optional[float] = None
    snowfall_12h: Optional[float] = None
    snowfall_24h: Optional[float] = None
    snowfall_7d: Optional[float] = None
    base_depth: Optional[float] = None
    precip_type: Optional[str] = None
    is_operational: Optional[bool] = None
    lifts_open: Optional[int] = None
    lifts_total: Optional[int] = None
    trails_open: Optional[int] = None
    trails_total: Optional[int] = None

    @staticmethod
    def now(resort_id: str, **kwargs: object) -> "ConditionSnapshot":
        return ConditionSnapshot(
            resort_id=resort_id,
            timestamp=datetime.now(timezone.utc),
            **kwargs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resort_id": self.resort_id,
            "timestamp": self.timestamp.isoformat(),
            "wind_speed": self.wind_speed,
            "wind_chill": self.wind_chill,
            "temp_min": self.temp_min,
            "temp_max": self.temp_max,
            "snowfall_12h": self.snowfall_12h,
            "snowfall_24h": self.snowfall_24h,
            "snowfall_7d": self.snowfall_7d,
            "base_depth": self.base_depth,
            "precip_type": self.precip_type,
            "is_operational": self.is_operational,
            "lifts_open": self.lifts_open,
            "lifts_total": self.lifts_total,
            "trails_open": self.trails_open,
            "trails_total": self.trails_total,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ConditionSnapshot":
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp_value = datetime.fromisoformat(timestamp)
        elif isinstance(timestamp, datetime):
            timestamp_value = timestamp
        else:
            raise TypeError("timestamp must be a datetime or ISO-8601 string")

        return cls(
            resort_id=data["resort_id"],
            timestamp=timestamp_value,
            wind_speed=data.get("wind_speed"),
            wind_chill=data.get("wind_chill"),
            temp_min=data.get("temp_min"),
            temp_max=data.get("temp_max"),
            snowfall_12h=data.get("snowfall_12h"),
            snowfall_24h=data.get("snowfall_24h"),
            snowfall_7d=data.get("snowfall_7d"),
            base_depth=data.get("base_depth"),
            precip_type=data.get("precip_type"),
            is_operational=data.get("is_operational"),
            lifts_open=data.get("lifts_open"),
            lifts_total=data.get("lifts_total"),
            trails_open=data.get("trails_open"),
            trails_total=data.get("trails_total"),
        )

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional


@dataclass
class Snowfall:
    last_12h: Optional[float] = None
    last_24h: Optional[float] = None
    last_7d: Optional[float] = None
    units: str = "in"


@dataclass
class Temperature:
    current: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None
    units: str = "F"


@dataclass
class ConditionSnapshot:
    resort_id: str
    fetched_at: datetime
    snowfall: Snowfall = field(default_factory=Snowfall)
    temperature: Temperature = field(default_factory=Temperature)
    wind_speed_mph: Optional[float] = None
    wind_direction: Optional[str] = None
    base_depth_in: Optional[float] = None
    lifts_open: Optional[int] = None
    lifts_total: Optional[int] = None
    lift_status: Dict[str, str] = field(default_factory=dict)
    raw_source: Optional[str] = None

    @staticmethod
    def now(resort_id: str, **kwargs: object) -> "ConditionSnapshot":
        return ConditionSnapshot(resort_id=resort_id, fetched_at=datetime.now(timezone.utc), **kwargs)

    def copy_with(self, **kwargs: object) -> "ConditionSnapshot":
        data = self.__dict__.copy()
        data.update(kwargs)
        return ConditionSnapshot(**data)

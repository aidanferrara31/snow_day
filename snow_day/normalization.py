from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional

from .models import ConditionSnapshot

Converter = Callable[[Any], Any]


@dataclass(frozen=True)
class FieldMapping:
    """Describes how to pull and transform a raw metric into a normalized field."""

    source: str
    converter: Optional[Converter] = None
    transform: Optional[Converter] = None

    def extract(self, payload: Mapping[str, Any]) -> Any:
        value = payload.get(self.source)
        if self.transform:
            value = self.transform(value)
        if self.converter and value is not None:
            value = self.converter(value)
        return value


class ConditionNormalizer:
    """Normalizes resort-specific payloads into :class:`ConditionSnapshot` objects."""

    def __init__(self, mappings: Mapping[str, Mapping[str, FieldMapping]]) -> None:
        self._mappings: Dict[str, Mapping[str, FieldMapping]] = dict(mappings)

    @staticmethod
    def _kph_to_mph(value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value) * 0.621371

    @staticmethod
    def _cm_to_inches(value: Any) -> Optional[float]:
        if value is None:
            return None
        return float(value) * 0.393701

    @staticmethod
    def _c_to_f(value: Any) -> Optional[float]:
        if value is None:
            return None
        return (float(value) * 9 / 5) + 32

    def normalize(
        self,
        resort_id: str,
        payload: Mapping[str, Any],
        *,
        timestamp: Optional[datetime] = None,
    ) -> ConditionSnapshot:
        mapping = self._mappings.get(resort_id, {})

        def resolve(field: str) -> Any:
            spec = mapping.get(field)
            if spec:
                return spec.extract(payload)
            return payload.get(field)

        return ConditionSnapshot(
            resort_id=resort_id,
            timestamp=timestamp or datetime.now(timezone.utc),
            wind_speed=resolve("wind_speed"),
            wind_chill=resolve("wind_chill"),
            temp_min=resolve("temp_min"),
            temp_max=resolve("temp_max"),
            snowfall_12h=resolve("snowfall_12h"),
            snowfall_24h=resolve("snowfall_24h"),
            snowfall_7d=resolve("snowfall_7d"),
            base_depth=resolve("base_depth"),
            precip_type=resolve("precip_type"),
        )


DEFAULT_NORMALIZER = ConditionNormalizer(
    mappings={
        "alpine_peak": {
            "wind_speed": FieldMapping("wind_speed_mph"),
            "wind_chill": FieldMapping("wind_chill_f"),
            "temp_min": FieldMapping("temp_low_f"),
            "temp_max": FieldMapping("temp_high_f"),
            "snowfall_12h": FieldMapping("snowfall_last_12h_in"),
            "snowfall_24h": FieldMapping("snowfall_last_24h_in"),
            "snowfall_7d": FieldMapping("snowfall_last_7d_in"),
            "base_depth": FieldMapping("base_depth_in"),
            "precip_type": FieldMapping("precip_type"),
        },
        "summit_valley": {
            "wind_speed": FieldMapping("wind_speed_mph"),
            "wind_chill": FieldMapping("wind_chill_f"),
            "temp_min": FieldMapping("temp_low_f"),
            "temp_max": FieldMapping("temp_high_f"),
            "snowfall_12h": FieldMapping("snowfall_last_12h_in"),
            "snowfall_24h": FieldMapping("snowfall_last_24h_in"),
            "snowfall_7d": FieldMapping("snowfall_last_7d_in"),
            "base_depth": FieldMapping("base_depth_in"),
            "precip_type": FieldMapping("precip_type"),
        },
    }
)

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional

import yaml
from dotenv import load_dotenv

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config" / "defaults.yaml"
load_dotenv()


def _bool_from_env(value: str | None) -> Optional[bool]:
    if value is None:
        return None
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _merge_dicts(base: Dict, overrides: Mapping) -> Dict:
    merged = dict(base)
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), Mapping):
            merged[key] = _merge_dicts(base[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml(path: Path) -> Dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


@dataclass
class SchedulerConfig:
    cron: str = "0 6,18 * * *"
    enabled: bool = True


@dataclass
class LoggingConfig:
    level: str = "INFO"
    json: bool = True


@dataclass
class ScraperSettings:
    report_url: str = ""
    selectors: Dict[str, str] = field(default_factory=dict)


@dataclass
class ResortSettings:
    id: str
    name: str
    state: str
    scraper: Optional[str] = None


@dataclass
class AppConfig:
    resorts: Iterable[ResortSettings] = field(default_factory=list)
    scrapers: Dict[str, ScraperSettings] = field(default_factory=dict)
    scoring: Dict[str, float] = field(default_factory=dict)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def load_config(*, config_path: str | None = None, env: Mapping[str, str] | None = None) -> AppConfig:
    env = dict(env or os.environ)
    data = _load_yaml(_DEFAULT_CONFIG_PATH)

    explicit_path = config_path or env.get("SNOWDAY_CONFIG_PATH")
    if explicit_path:
        data = _merge_dicts(data, _load_yaml(Path(explicit_path)))

    scheduler_data = data.get("scheduler", {})
    cron_override = env.get("SNOWDAY_SCHEDULER_CRON")
    if cron_override:
        scheduler_data["cron"] = cron_override
    enabled_override = _bool_from_env(env.get("SNOWDAY_SCHEDULER_ENABLED"))
    if enabled_override is not None:
        scheduler_data["enabled"] = enabled_override

    logging_data = data.get("logging", {})
    level_override = env.get("SNOWDAY_LOG_LEVEL")
    if level_override:
        logging_data["level"] = level_override
    json_override = _bool_from_env(env.get("SNOWDAY_LOG_JSON"))
    if json_override is not None:
        logging_data["json"] = json_override

    scoring_data: Dict[str, float] = data.get("scoring", {})
    prefix = "SNOWDAY_SCORING_"
    for key, value in env.items():
        if key.startswith(prefix):
            field_name = key.removeprefix(prefix).lower()
            try:
                scoring_data[field_name] = float(value)
            except ValueError:
                continue

    resorts = [ResortSettings(**resort) for resort in data.get("resorts", [])]
    scrapers = {
        key: ScraperSettings(**details) for key, details in data.get("scrapers", {}).items()
    }

    return AppConfig(
        resorts=resorts,
        scrapers=scrapers,
        scoring=scoring_data,
        scheduler=SchedulerConfig(**scheduler_data) if scheduler_data else SchedulerConfig(),
        logging=LoggingConfig(**logging_data) if logging_data else LoggingConfig(),
    )


app_config = load_config()

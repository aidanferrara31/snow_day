from __future__ import annotations

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from snow_day.cache import LastModifiedCache
from snow_day.config import app_config
from snow_day.logging import get_logger, setup_logging
from snow_day.models import ConditionSnapshot
from snow_day.resorts import ResortMeta, all_resorts, resort_lookup
from snow_day.scheduler import build_scheduler
from snow_day.scrapers import SCRAPERS, fetch_conditions
from snow_day.services.llm_client import LLMClient, ScoredResort
from snow_day.services.scoring import ScoreResult, ScoringConfig, score_snapshot
from snow_day.services.weather import fetch_current_weather
from snow_day.storage import ConditionStore

setup_logging(app_config.logging)
logger = get_logger(__name__)

app = FastAPI(title="Snow Day API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConditionPayload(BaseModel):
    resort_id: str
    name: str
    state: str
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


class RankingPayload(BaseModel):
    resort_id: str
    name: str
    state: str
    score: float
    rationale: str
    powder: bool
    icy: bool
    conditions: ConditionPayload


class RankingsResponse(BaseModel):
    updated_at: Optional[datetime]
    rankings: List[RankingPayload]
    summary: str


class ConditionsResponse(BaseModel):
    updated_at: Optional[datetime]
    resorts: List[ConditionPayload]


store = ConditionStore()
cache = LastModifiedCache()
llm_client = LLMClient()
scoring_config = ScoringConfig.from_sources(config_data=app_config.scoring)

_resorts: List[ResortMeta] = all_resorts()
_resort_index: Dict[str, ResortMeta] = resort_lookup(_resorts)


def _augment_with_weather(snapshot: ConditionSnapshot, *, trace_id: Optional[str] = None) -> ConditionSnapshot:
    resort = _resort_index.get(snapshot.resort_id)
    if not resort or resort.latitude is None or resort.longitude is None:
        return snapshot

    needs_temp = snapshot.temp_max is None and snapshot.temp_min is None
    needs_wind = snapshot.wind_speed is None
    if not (needs_temp or needs_wind):
        return snapshot

    try:
        observation = fetch_current_weather(resort.latitude, resort.longitude)
    except Exception as exc:  # pragma: no cover - network fallback
        logger.warning(
            "weather.fallback_failed",
            trace_id=trace_id,
            resort_id=snapshot.resort_id,
            error=str(exc),
        )
        return snapshot

    if needs_temp and observation.temperature_f is not None:
        snapshot.temp_max = observation.temperature_f
        snapshot.temp_min = observation.temperature_f
    if needs_wind and observation.wind_speed_mph is not None:
        snapshot.wind_speed = observation.wind_speed_mph

    logger.info(
        "weather.fallback_applied",
        trace_id=trace_id,
        resort_id=snapshot.resort_id,
    )
    return snapshot


def _infer_operational_status(snapshot: ConditionSnapshot) -> ConditionSnapshot:
    """Infer operational status for ALL resorts, overriding incorrect False status.
    
    If a resort has open trails or lifts, it MUST be open, regardless of what
    the scraper reported. This fixes cases where scrapers incorrectly mark
    resorts as closed.
    """
    # Strongest signal: if trails or lifts are open, resort MUST be open
    # This overrides any False status from scrapers
    if (snapshot.trails_open or 0) > 0:
        snapshot.is_operational = True
        return snapshot
    
    if (snapshot.lifts_open or 0) > 0:
        snapshot.is_operational = True
        return snapshot
    
    # If already explicitly True, keep it
    if snapshot.is_operational is True:
        return snapshot
    
    # If status is unknown (None), try to infer from other signals
    if snapshot.is_operational is None:
        if (snapshot.base_depth or 0) >= 6:
            snapshot.is_operational = True
        elif (snapshot.snowfall_24h or snapshot.snowfall_12h or 0) > 0:
            snapshot.is_operational = True
    
    # If status is False and we don't have trails/lifts data, leave it as False
    # (resort might actually be closed)
    return snapshot


def _snapshot_to_payload(snapshot: ConditionSnapshot) -> ConditionPayload:
    resort = _resort_index.get(snapshot.resort_id)
    return ConditionPayload(
        resort_id=snapshot.resort_id,
        name=resort.name if resort else snapshot.resort_id,
        state=resort.state if resort else "",
        timestamp=snapshot.timestamp,
        wind_speed=snapshot.wind_speed,
        wind_chill=snapshot.wind_chill,
        temp_min=snapshot.temp_min,
        temp_max=snapshot.temp_max,
        snowfall_12h=snapshot.snowfall_12h,
        snowfall_24h=snapshot.snowfall_24h,
        snowfall_7d=snapshot.snowfall_7d,
        base_depth=snapshot.base_depth,
        precip_type=snapshot.precip_type,
        is_operational=snapshot.is_operational,
        lifts_open=snapshot.lifts_open,
        lifts_total=snapshot.lifts_total,
        trails_open=snapshot.trails_open,
        trails_total=snapshot.trails_total,
    )


def _latest_snapshots() -> List[ConditionSnapshot]:
    """Get latest snapshots from storage and apply operational status inference."""
    snapshots: List[ConditionSnapshot] = []
    for resort_id in SCRAPERS.keys():
        latest = store.get_latest(resort_id)
        if latest:
            # Apply operational status inference to fix incorrect closed status
            latest = _infer_operational_status(latest)
            snapshots.append(latest)
    return snapshots


def _score_resorts() -> RankingsResponse:
    ranked: List[RankingPayload] = []
    scored_resorts: List[ScoredResort] = []
    snapshots = _latest_snapshots()
    updated_at: Optional[datetime] = None

    for snapshot in snapshots:
        previous = store.list_snapshots(snapshot.resort_id, limit=5)[1:]
        result: ScoreResult = score_snapshot(snapshot, previous_snapshots=previous, config=scoring_config)
        payload = _snapshot_to_payload(snapshot)
        resort = _resort_index.get(snapshot.resort_id)
        ranked.append(
            RankingPayload(
                resort_id=snapshot.resort_id,
                name=resort.name if resort else snapshot.resort_id,
                state=resort.state if resort else "",
                score=result.score,
                rationale=result.rationale,
                powder=result.powder,
                icy=result.icy,
                conditions=payload,
            )
        )
        scored_resorts.append(
            ScoredResort.from_result(
                payload.name,
                result,
                snowfall_24h=snapshot.snowfall_24h,
                snowfall_12h=snapshot.snowfall_12h,
                base_depth=snapshot.base_depth,
                wind_speed=snapshot.wind_speed,
                temp_min=snapshot.temp_min,
                temp_max=snapshot.temp_max,
                precip_type=snapshot.precip_type,
                is_operational=snapshot.is_operational,
                lifts_open=snapshot.lifts_open,
                lifts_total=snapshot.lifts_total,
                trails_open=snapshot.trails_open,
                trails_total=snapshot.trails_total,
            )
        )
        if updated_at is None or snapshot.timestamp > updated_at:
            updated_at = snapshot.timestamp

    ranked.sort(key=lambda item: item.score, reverse=True)
    summary = llm_client.summarize_top_resorts(scored_resorts, top_n=3)
    return RankingsResponse(updated_at=updated_at, rankings=ranked, summary=summary)


def refresh_and_score() -> RankingsResponse:
    logger.info("refresh.start")
    for resort_id in SCRAPERS.keys():
        trace_id = uuid.uuid4().hex
        try:
            snapshot = fetch_conditions(resort_id, cache=cache, trace_id=trace_id)
            snapshot = _augment_with_weather(snapshot, trace_id=trace_id)
            snapshot = _infer_operational_status(snapshot)
            store.add_snapshot(snapshot)
        except Exception as exc:  # pragma: no cover - surface partial refresh when scrapes fail
            logger.error(
                "refresh.error",
                trace_id=trace_id,
                resort_id=resort_id,
                error=str(exc),
            )
            continue
    logger.info("refresh.complete")
    return _score_resorts()


@app.get("/conditions", response_model=ConditionsResponse)
def get_conditions() -> ConditionsResponse:
    snapshots = _latest_snapshots()
    payloads = [_snapshot_to_payload(snapshot) for snapshot in snapshots]
    updated_at = max((snapshot.timestamp for snapshot in snapshots), default=None)
    return ConditionsResponse(updated_at=updated_at, resorts=payloads)


@app.get("/rankings", response_model=RankingsResponse)
def get_rankings() -> RankingsResponse:
    return _score_resorts()


@app.post("/refresh", response_model=RankingsResponse)
def refresh_conditions() -> RankingsResponse:
    return refresh_and_score()


_scheduler = build_scheduler(refresh_and_score, app_config.scheduler)


@app.on_event("startup")
async def _start_scheduler() -> None:
    if _scheduler and not _scheduler.running:
        logger.info("scheduler.start")
        _scheduler.start()


@app.on_event("shutdown")
async def _stop_scheduler() -> None:
    if _scheduler and _scheduler.running:
        logger.info("scheduler.stop")
        _scheduler.shutdown()

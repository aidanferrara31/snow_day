from datetime import datetime, timedelta, timezone
from pathlib import Path

from snow_day.models import ConditionSnapshot
from snow_day.storage import ConditionStore


def build_snapshot(resort_id: str, *, timestamp: datetime) -> ConditionSnapshot:
    return ConditionSnapshot(
        resort_id=resort_id,
        timestamp=timestamp,
        wind_speed=5.0,
        wind_chill=-5.0,
        temp_min=10.0,
        temp_max=20.0,
        snowfall_12h=1.0,
        snowfall_24h=2.0,
        snowfall_7d=5.0,
        base_depth=30.0,
        precip_type="snow",
    )


def test_store_persists_and_fetches_snapshots(tmp_path: Path):
    db_path = tmp_path / "conditions.db"
    store = ConditionStore(db_path)

    ts = datetime(2024, 2, 1, tzinfo=timezone.utc)
    snapshot = build_snapshot("alpine_peak", timestamp=ts)
    store.add_snapshot(snapshot)

    latest = store.get_latest("alpine_peak")
    assert latest == snapshot

    all_snapshots = store.list_snapshots("alpine_peak")
    assert len(all_snapshots) == 1


def test_prune_respects_age_and_keep_last(tmp_path: Path):
    db_path = tmp_path / "conditions.db"
    store = ConditionStore(db_path)

    now = datetime.now(timezone.utc)
    snapshots = [
        build_snapshot("summit_valley", timestamp=now - timedelta(hours=4)),
        build_snapshot("summit_valley", timestamp=now - timedelta(hours=2)),
        build_snapshot("summit_valley", timestamp=now - timedelta(hours=1)),
    ]
    for snap in snapshots:
        store.add_snapshot(snap)

    deleted = store.prune(resort_id="summit_valley", max_age=timedelta(hours=3))
    assert deleted == 1

    # Keep only the most recent snapshot
    deleted += store.prune(resort_id="summit_valley", keep_last=1)
    assert deleted == 2

    remaining = store.list_snapshots("summit_valley")
    assert len(remaining) == 1
    assert remaining[0].timestamp == snapshots[-1].timestamp

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from .models import ConditionSnapshot


class ConditionStore:
    """Persists normalized condition snapshots to a SQLite database."""

    def __init__(self, db_path: Path | str = Path("data/conditions.db")) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resort_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    wind_speed REAL,
                    wind_chill REAL,
                    temp_min REAL,
                    temp_max REAL,
                    snowfall_12h REAL,
                    snowfall_24h REAL,
                    snowfall_7d REAL,
                    base_depth REAL,
                    precip_type TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_snapshots_resort_ts
                ON snapshots(resort_id, timestamp)
                """
            )

    def add_snapshot(self, snapshot: ConditionSnapshot) -> None:
        data = snapshot.to_dict()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO snapshots (
                    resort_id, timestamp, wind_speed, wind_chill, temp_min, temp_max,
                    snowfall_12h, snowfall_24h, snowfall_7d, base_depth, precip_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["resort_id"],
                    data["timestamp"],
                    data["wind_speed"],
                    data["wind_chill"],
                    data["temp_min"],
                    data["temp_max"],
                    data["snowfall_12h"],
                    data["snowfall_24h"],
                    data["snowfall_7d"],
                    data["base_depth"],
                    data.get("precip_type"),
                ),
            )

    def get_latest(self, resort_id: str) -> Optional[ConditionSnapshot]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT resort_id, timestamp, wind_speed, wind_chill, temp_min, temp_max,
                       snowfall_12h, snowfall_24h, snowfall_7d, base_depth, precip_type
                FROM snapshots
                WHERE resort_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (resort_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_snapshot(row)

    def list_snapshots(
        self, resort_id: Optional[str] = None, limit: Optional[int] = None
    ) -> List[ConditionSnapshot]:
        query = (
            "SELECT resort_id, timestamp, wind_speed, wind_chill, temp_min, temp_max,"
            " snowfall_12h, snowfall_24h, snowfall_7d, base_depth, precip_type FROM snapshots"
        )
        params: List[object] = []
        if resort_id:
            query += " WHERE resort_id = ?"
            params.append(resort_id)
        query += " ORDER BY timestamp DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()

        return [self._row_to_snapshot(row) for row in rows]

    def delete_snapshot(self, resort_id: str, timestamp: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM snapshots WHERE resort_id = ? AND timestamp = ?",
                (resort_id, timestamp.isoformat()),
            )

    def prune(
        self,
        *,
        resort_id: Optional[str] = None,
        max_age: Optional[timedelta] = None,
        keep_last: Optional[int] = None,
    ) -> int:
        """Remove old snapshots based on age or a maximum count.

        Returns the number of deleted rows.
        """

        deleted = 0
        with self._connect() as conn:
            if max_age is not None:
                cutoff = datetime.now(timezone.utc) - max_age
                params: List[object] = [cutoff.isoformat()]
                clause = "timestamp < ?"
                if resort_id:
                    clause += " AND resort_id = ?"
                    params.append(resort_id)
                deleted += conn.execute(
                    f"DELETE FROM snapshots WHERE {clause}", tuple(params)
                ).rowcount

            if keep_last is not None:
                deleted += self._prune_keep_last(conn, keep_last, resort_id)

        return deleted

    def _prune_keep_last(
        self, conn: sqlite3.Connection, keep_last: int, resort_id: Optional[str]
    ) -> int:
        deleted = 0
        resorts: Iterable[str]
        if resort_id:
            resorts = [resort_id]
        else:
            resorts = [row[0] for row in conn.execute("SELECT DISTINCT resort_id FROM snapshots")]

        for rid in resorts:
            rows = conn.execute(
                """
                SELECT rowid FROM snapshots
                WHERE resort_id = ?
                ORDER BY timestamp DESC
                LIMIT -1 OFFSET ?
                """,
                (rid, keep_last),
            ).fetchall()
            if rows:
                deleted += conn.execute(
                    "DELETE FROM snapshots WHERE rowid IN (%s)" % (
                        ",".join(str(row[0]) for row in rows)
                    )
                ).rowcount
        return deleted

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row | tuple) -> ConditionSnapshot:
        (
            resort_id,
            timestamp,
            wind_speed,
            wind_chill,
            temp_min,
            temp_max,
            snowfall_12h,
            snowfall_24h,
            snowfall_7d,
            base_depth,
            precip_type,
        ) = row
        return ConditionSnapshot.from_dict(
            {
                "resort_id": resort_id,
                "timestamp": timestamp,
                "wind_speed": wind_speed,
                "wind_chill": wind_chill,
                "temp_min": temp_min,
                "temp_max": temp_max,
                "snowfall_12h": snowfall_12h,
                "snowfall_24h": snowfall_24h,
                "snowfall_7d": snowfall_7d,
                "base_depth": base_depth,
                "precip_type": precip_type,
            }
        )

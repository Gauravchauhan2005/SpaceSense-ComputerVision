"""
SpaceSense AI — Database Manager

Async SQLite database for session persistence.  Designed with an abstract
interface so PostgreSQL can replace SQLite later.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data") / "spacesense.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    start_time REAL NOT NULL,
    end_time REAL,
    duration_seconds REAL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS session_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    face_distance_cm REAL,
    left_hand_distance_cm REAL,
    right_hand_distance_cm REAL,
    closest_object TEXT,
    ergonomic_state TEXT,
    fps REAL,
    hand_movement_speed REAL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS session_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT UNIQUE NOT NULL,
    avg_face_distance REAL,
    min_face_distance REAL,
    max_face_distance REAL,
    avg_hand_speed REAL,
    warning_count INTEGER DEFAULT 0,
    critical_count INTEGER DEFAULT 0,
    total_duration REAL DEFAULT 0,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS calibrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""


class DatabaseManager:
    """Async SQLite database manager.

    Parameters
    ----------
    db_path : str or Path
        Path to the SQLite database file.
    """

    def __init__(self, db_path: str | Path = _DEFAULT_DB_PATH) -> None:
        self._db_path = Path(db_path)
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Create the database file and tables if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA_SQL)
        await self._db.commit()
        logger.info("Database initialized at %s", self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._db

    # ── Sessions ──

    async def create_session(self) -> str:
        """Create a new session and return its ID."""
        session_id = str(uuid.uuid4())[:8]
        now = time.time()
        await self.db.execute(
            "INSERT INTO sessions (id, start_time, created_at) VALUES (?, ?, ?)",
            (session_id, now, now),
        )
        await self.db.commit()
        return session_id

    async def end_session(self, session_id: str) -> None:
        """Mark a session as ended."""
        now = time.time()
        await self.db.execute(
            "UPDATE sessions SET end_time = ?, duration_seconds = end_time - start_time WHERE id = ?",
            (now, session_id),
        )
        await self.db.commit()

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """Return all sessions with summaries."""
        cursor = await self.db.execute(
            """SELECT s.id, s.start_time, s.end_time, s.duration_seconds,
                      ss.avg_face_distance, ss.min_face_distance,
                      ss.warning_count, ss.critical_count
               FROM sessions s
               LEFT JOIN session_summaries ss ON s.id = ss.session_id
               ORDER BY s.start_time DESC"""
        )
        rows = await cursor.fetchall()
        return [
            {
                "session_id": r["id"],
                "start_time": r["start_time"],
                "end_time": r["end_time"],
                "duration_seconds": r["duration_seconds"] or 0,
                "avg_distance_cm": r["avg_face_distance"],
                "warning_count": r["warning_count"] or 0,
                "critical_count": r["critical_count"] or 0,
            }
            for r in rows
        ]

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a session with its metrics."""
        cursor = await self.db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        metrics_cursor = await self.db.execute(
            "SELECT * FROM session_metrics WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        metrics = await metrics_cursor.fetchall()

        return {
            "session_id": row["id"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "duration_seconds": row["duration_seconds"] or 0,
            "metrics": [dict(m) for m in metrics],
        }

    async def delete_session(self, session_id: str) -> None:
        """Delete a session and its data."""
        await self.db.execute("DELETE FROM session_metrics WHERE session_id = ?", (session_id,))
        await self.db.execute("DELETE FROM session_summaries WHERE session_id = ?", (session_id,))
        await self.db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await self.db.commit()

    async def insert_metric(self, session_id: str, data: Dict[str, Any]) -> None:
        """Insert a single metric record."""
        await self.db.execute(
            """INSERT INTO session_metrics
               (session_id, timestamp, face_distance_cm, left_hand_distance_cm,
                right_hand_distance_cm, closest_object, ergonomic_state, fps, hand_movement_speed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                data.get("timestamp", time.time()),
                data.get("face_distance_cm"),
                data.get("left_hand_distance_cm"),
                data.get("right_hand_distance_cm"),
                data.get("closest_object"),
                data.get("ergonomic_state"),
                data.get("fps"),
                data.get("hand_movement_speed"),
            ),
        )
        await self.db.commit()

    async def update_summary(self, session_id: str, summary: Dict[str, Any]) -> None:
        """Upsert session summary."""
        await self.db.execute(
            """INSERT INTO session_summaries
               (session_id, avg_face_distance, min_face_distance, max_face_distance,
                avg_hand_speed, warning_count, critical_count, total_duration)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                avg_face_distance = excluded.avg_face_distance,
                min_face_distance = excluded.min_face_distance,
                max_face_distance = excluded.max_face_distance,
                avg_hand_speed = excluded.avg_hand_speed,
                warning_count = excluded.warning_count,
                critical_count = excluded.critical_count,
                total_duration = excluded.total_duration""",
            (
                session_id,
                summary.get("avg_face_distance"),
                summary.get("min_face_distance"),
                summary.get("max_face_distance"),
                summary.get("avg_hand_speed"),
                summary.get("warning_count", 0),
                summary.get("critical_count", 0),
                summary.get("total_duration", 0),
            ),
        )
        await self.db.commit()

    async def export_session_csv_data(self, session_id: str) -> List[Dict[str, Any]]:
        """Return all metric rows for CSV export."""
        cursor = await self.db.execute(
            "SELECT * FROM session_metrics WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

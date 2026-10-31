"""
SpaceSense AI — Session Manager

Manages tracking session lifecycle: start, record metrics, stop, and query.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from backend.database.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class SessionManager:
    """High-level session management on top of DatabaseManager.

    Parameters
    ----------
    db : DatabaseManager
        The database manager instance.
    """

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db
        self._current_session_id: Optional[str] = None
        self._face_distances: list[float] = []
        self._hand_speeds: list[float] = []

    @property
    def current_session_id(self) -> Optional[str]:
        return self._current_session_id

    async def start_session(self) -> str:
        """Start a new session. Returns session ID."""
        if self._current_session_id is not None:
            await self.stop_session()

        session_id = await self._db.create_session()
        self._current_session_id = session_id
        self._face_distances.clear()
        self._hand_speeds.clear()
        logger.info("Session started: %s", session_id)
        return session_id

    async def stop_session(self) -> None:
        """End the current session and save summary."""
        if self._current_session_id is None:
            return

        await self._db.end_session(self._current_session_id)

        # Calculate summary
        summary: Dict[str, Any] = {
            "avg_face_distance": (
                sum(self._face_distances) / len(self._face_distances)
                if self._face_distances else None
            ),
            "min_face_distance": min(self._face_distances) if self._face_distances else None,
            "max_face_distance": max(self._face_distances) if self._face_distances else None,
            "avg_hand_speed": (
                sum(self._hand_speeds) / len(self._hand_speeds)
                if self._hand_speeds else None
            ),
        }
        await self._db.update_summary(self._current_session_id, summary)

        logger.info("Session stopped: %s", self._current_session_id)
        self._current_session_id = None

    async def save_metrics(self, tracking_data: Dict[str, Any]) -> None:
        """Save a snapshot of tracking data to the current session."""
        if self._current_session_id is None:
            return

        face = tracking_data.get("face", {})
        hands = tracking_data.get("hands", [])
        ergo = tracking_data.get("ergonomic", {})
        closest = tracking_data.get("closest_object", {})

        face_dist = face.get("distance_cm")
        left_dist = None
        right_dist = None
        hand_speed = None

        for h in hands:
            if h.get("label") == "Left":
                left_dist = h.get("distance_cm")
            elif h.get("label") == "Right":
                right_dist = h.get("distance_cm")
            mov = h.get("movement", {})
            if mov:
                speed = mov.get("speed_px_per_sec", 0)
                if speed:
                    hand_speed = speed

        if face_dist is not None:
            self._face_distances.append(face_dist)
        if hand_speed is not None:
            self._hand_speeds.append(hand_speed)

        await self._db.insert_metric(self._current_session_id, {
            "timestamp": tracking_data.get("timestamp", time.time()),
            "face_distance_cm": face_dist,
            "left_hand_distance_cm": left_dist,
            "right_hand_distance_cm": right_dist,
            "closest_object": closest.get("name") if closest else None,
            "ergonomic_state": ergo.get("state") if ergo else None,
            "fps": tracking_data.get("fps"),
            "hand_movement_speed": hand_speed,
        })

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Sync wrapper — delegates to async."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't await from sync context inside running loop
                # Return empty — use async version from routes
                return []
        except RuntimeError:
            pass
        return asyncio.run(self._db.list_sessions())

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Sync wrapper."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return None
        except RuntimeError:
            pass
        return asyncio.run(self._db.get_session(session_id))

    def delete_session(self, session_id: str) -> None:
        """Sync wrapper."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return
        except RuntimeError:
            pass
        asyncio.run(self._db.delete_session(session_id))

    def export_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Sync wrapper."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return []
        except RuntimeError:
            pass
        return asyncio.run(self._db.export_session_csv_data(session_id))

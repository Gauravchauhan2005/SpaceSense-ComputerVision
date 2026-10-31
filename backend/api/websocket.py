"""
SpaceSense AI — WebSocket Handler

Real-time streaming of tracking data and annotated video frames
to connected browser clients via ``/ws/tracking``.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger("spacesense.websocket")


# ────────────────────────────────────────────────────────────────────
# Connection Manager
# ────────────────────────────────────────────────────────────────────

class ConnectionManager:
    """
    Manages concurrent WebSocket clients.

    Thread-safe add/remove (uses asyncio locks). Broadcasts are
    fire-and-forget per client so one slow consumer never blocks others.
    """

    def __init__(self) -> None:
        self._active: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        # Frame broadcast cadence — 1 means every frame, 3 means every 3rd, etc.
        self.frame_send_interval: int = 2
        self._frame_counter: int = 0

    @property
    def active_count(self) -> int:
        return len(self._active)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and register it."""
        await websocket.accept()
        async with self._lock:
            self._active.add(websocket)
        logger.info("WebSocket client connected. Active: %d", self.active_count)

        # Send connection confirmation
        await self._safe_send_json(websocket, {
            "type": "connection",
            "status": "connected",
            "timestamp": time.time(),
            "message": "SpaceSense AI tracking stream connected.",
        })

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket connection."""
        async with self._lock:
            self._active.discard(websocket)
        logger.info("WebSocket client disconnected. Active: %d", self.active_count)

    async def broadcast_tracking_data(self, data: Dict[str, Any]) -> None:
        """Send a tracking-data payload to all connected clients."""
        if not self._active:
            return
        payload = json.dumps(data)
        async with self._lock:
            clients = list(self._active)
        stale: List[WebSocket] = []
        for ws in clients:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await asyncio.wait_for(ws.send_text(payload), timeout=2.0)
            except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError, Exception):
                stale.append(ws)
        if stale:
            async with self._lock:
                for ws in stale:
                    self._active.discard(ws)

    async def broadcast_frame(
        self,
        frame_bytes: bytes,
        width: int,
        height: int,
    ) -> None:
        """
        Encode a JPEG frame as base64 and broadcast it as a ``frame``
        message.  Respects ``frame_send_interval`` to avoid flooding.
        """
        self._frame_counter += 1
        if self._frame_counter % self.frame_send_interval != 0:
            return
        if not self._active:
            return

        b64 = base64.b64encode(frame_bytes).decode("ascii")
        payload = json.dumps({
            "type": "frame",
            "data": b64,
            "width": width,
            "height": height,
        })

        async with self._lock:
            clients = list(self._active)
        stale: List[WebSocket] = []
        for ws in clients:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await asyncio.wait_for(ws.send_text(payload), timeout=2.0)
            except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError, Exception):
                stale.append(ws)
        if stale:
            async with self._lock:
                for ws in stale:
                    self._active.discard(ws)

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    async def _safe_send_json(ws: WebSocket, data: dict) -> bool:
        """Send JSON to a single WebSocket, swallowing errors."""
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.send_json(data)
                return True
        except Exception:
            pass
        return False


# Singleton instance — imported by main.py and the WebSocket endpoint
manager = ConnectionManager()


# ────────────────────────────────────────────────────────────────────
# WebSocket Endpoint
# ────────────────────────────────────────────────────────────────────

async def tracking_websocket_endpoint(websocket: WebSocket) -> None:
    """
    ``/ws/tracking`` handler.

    After accepting the connection the server enters a receive-loop
    that handles ping/pong keep-alive and configuration messages from
    the client (e.g. adjusting ``frame_send_interval``).

    Tracking data is *pushed* to the client by the main processing
    loop via :pymethod:`ConnectionManager.broadcast_tracking_data` and
    :pymethod:`ConnectionManager.broadcast_frame`.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Wait for client messages (pings / config changes)
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
            except asyncio.TimeoutError:
                # Send a server-side ping to keep the connection alive
                try:
                    await manager._safe_send_json(websocket, {
                        "type": "ping",
                        "timestamp": time.time(),
                    })
                except Exception:
                    break
                continue

            # Parse client message
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await manager._safe_send_json(websocket, {
                    "type": "pong",
                    "timestamp": time.time(),
                })

            elif msg_type == "pong":
                # Client responded to our ping — connection alive
                pass

            elif msg_type == "config":
                # Allow client to adjust frame send interval at runtime
                interval = msg.get("frame_send_interval")
                if isinstance(interval, int) and interval >= 1:
                    manager.frame_send_interval = interval
                    await manager._safe_send_json(websocket, {
                        "type": "config_ack",
                        "frame_send_interval": manager.frame_send_interval,
                        "timestamp": time.time(),
                    })

            elif msg_type == "get_status":
                await manager._safe_send_json(websocket, {
                    "type": "status",
                    "active_clients": manager.active_count,
                    "frame_send_interval": manager.frame_send_interval,
                    "timestamp": time.time(),
                })

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
    finally:
        await manager.disconnect(websocket)

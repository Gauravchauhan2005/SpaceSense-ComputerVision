"""
SpaceSense AI — Camera Management Module

Thread-safe camera capture using OpenCV VideoCapture.
Runs frame acquisition in a background thread so the async event loop
is never blocked.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

import cv2
import numpy as np

from backend.models import CameraInfoResponse, CameraStatus

logger = logging.getLogger(__name__)

# Common resolution presets (width, height)
RESOLUTION_PRESETS: dict[str, tuple[int, int]] = {
    "480p": (640, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
}


class CameraManager:
    """Manages an OpenCV VideoCapture device with background-threaded capture.

    Parameters
    ----------
    device_index : int
        Camera device index (0 = default webcam).
    resolution : tuple[int, int]
        Desired (width, height) in pixels. Default (640, 480).
    fps : int
        Desired capture frame-rate. Default 30.
    auto_start : bool
        If True the capture thread starts immediately on construction.
    """

    def __init__(
        self,
        device_index: int = 0,
        resolution: tuple[int, int] = (640, 480),
        fps: int = 30,
        auto_start: bool = False,
    ) -> None:
        self._device_index: int = device_index
        self._requested_resolution: tuple[int, int] = resolution
        self._requested_fps: int = fps

        # Internals
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock: threading.Lock = threading.Lock()
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._status: CameraStatus = CameraStatus.DISCONNECTED

        # Metrics
        self._actual_fps: float = 0.0
        self._frame_count: int = 0
        self._fps_timer: float = time.monotonic()

        # Optional per-frame callback
        self._frame_callback: Optional[Callable[[np.ndarray], None]] = None

        if auto_start:
            self.start()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def detect_available_cameras(max_index: int = 5) -> list[int]:
        """Probe camera indices 0 … max_index-1 and return those that open."""
        available: list[int] = []
        for idx in range(max_index):
            # Try DSHOW first on Windows, then CAP_ANY
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap = cv2.VideoCapture(idx, cv2.CAP_ANY)
            if cap.isOpened():
                available.append(idx)
                cap.release()
        return available

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(
        self,
        device_index: Optional[int] = None,
        resolution: Optional[tuple[int, int]] = None,
        fps: Optional[int] = None,
    ) -> bool:
        """Open the camera and spin up the capture thread.

        Accepts optional override parameters for device index, resolution, and fps.
        Returns True if the camera was opened successfully.
        """
        # Check if settings changed while running
        needs_restart = False
        if device_index is not None and device_index != self._device_index:
            self._device_index = device_index
            needs_restart = True
        if resolution is not None and resolution != self._requested_resolution:
            self._requested_resolution = resolution
            needs_restart = True
        if fps is not None and fps != self._requested_fps:
            self._requested_fps = fps
            needs_restart = True

        if self._running:
            if not needs_restart:
                logger.info("Camera %d already running.", self._device_index)
                return True
            logger.info("Camera settings changed, restarting...")
            self.stop()

        self._status = CameraStatus.INITIALIZING
        try:
            # On Windows, DirectShow (CAP_DSHOW) opens much faster and avoids freezes
            self._cap = cv2.VideoCapture(self._device_index, cv2.CAP_DSHOW)
            if not self._cap.isOpened():
                self._cap = cv2.VideoCapture(self._device_index, cv2.CAP_ANY)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to create VideoCapture for device %d: %s",
                         self._device_index, exc)
            self._status = CameraStatus.ERROR
            return False

        if not self._cap.isOpened():
            logger.error("Cannot open camera %d — permission denied or device unavailable.",
                         self._device_index)
            self._status = CameraStatus.ERROR
            return False

        # Apply requested settings
        w, h = self._requested_resolution
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
        self._cap.set(cv2.CAP_PROP_FPS, self._requested_fps)

        self._status = CameraStatus.CONNECTED
        self._running = True
        self._frame_count = 0
        self._fps_timer = time.monotonic()

        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"camera-{self._device_index}",
            daemon=True,
        )
        self._thread.start()
        logger.info("Camera %d started at %dx%d @ %d fps (requested).",
                     self._device_index, w, h, self._requested_fps)
        return True

    def stop(self) -> None:
        """Signal the capture thread to stop and release the camera."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._cap is not None:
            self._cap.release()
            self._cap = None

        self._status = CameraStatus.DISCONNECTED
        logger.info("Camera %d stopped.", self._device_index)

    def restart(self) -> bool:
        """Stop and re-open the camera. Returns True on success."""
        logger.info("Restarting camera %d …", self._device_index)
        self.stop()
        time.sleep(0.3)
        return self.start()

    # ------------------------------------------------------------------
    # Frame access
    # ------------------------------------------------------------------

    def get_frame(self) -> Optional[np.ndarray]:
        """Return the latest captured frame (BGR ndarray), or None."""
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def get_frame_jpeg(self, quality: int = 80) -> Optional[bytes]:
        """Return the latest frame encoded as JPEG bytes, or None."""
        frame = self.get_frame()
        if frame is None:
            return None
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        ok, buf = cv2.imencode(".jpg", frame, encode_params)
        if not ok:
            return None
        return buf.tobytes()

    # ------------------------------------------------------------------
    # Callback
    # ------------------------------------------------------------------

    def set_frame_callback(self, callback: Optional[Callable[[np.ndarray], None]]) -> None:
        """Register (or clear) a callback invoked on every captured frame."""
        self._frame_callback = callback

    # ------------------------------------------------------------------
    # Status / info properties
    # ------------------------------------------------------------------

    @property
    def status(self) -> CameraStatus:
        return self._status

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_capturing(self) -> bool:
        return self._running

    @property
    def is_connected(self) -> bool:
        return self._status == CameraStatus.CONNECTED

    @property
    def actual_fps(self) -> float:
        return self._actual_fps

    @property
    def device_index(self) -> int:
        return self._device_index

    @property
    def resolution(self) -> tuple[int, int]:
        """Return the actual resolution reported by the device."""
        if self._cap is not None and self._cap.isOpened():
            w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if w > 0 and h > 0:
                return (w, h)
        return self._requested_resolution

    def get_camera_info(self) -> CameraInfoResponse:
        """Return a Pydantic model with current camera information."""
        w, h = self.resolution
        return CameraInfoResponse(
            device_index=self._device_index,
            resolution_width=w,
            resolution_height=h,
            fps=round(self._actual_fps, 1),
            status=self._status,
        )

    # ------------------------------------------------------------------
    # Capture thread
    # ------------------------------------------------------------------

    def _capture_loop(self) -> None:
        """Continuously read frames until _running is cleared."""
        consecutive_failures: int = 0
        max_failures: int = 30  # ~1 s at 30 fps

        while self._running:
            if self._cap is None or not self._cap.isOpened():
                self._status = CameraStatus.DISCONNECTED
                logger.error("Camera %d: device lost.", self._device_index)
                break

            ok, frame = self._cap.read()
            if not ok or frame is None:
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    self._status = CameraStatus.ERROR
                    logger.error("Camera %d: too many consecutive read failures.",
                                 self._device_index)
                    break
                time.sleep(0.01)
                continue

            consecutive_failures = 0

            # Thread-safe frame update
            with self._lock:
                self._frame = frame

            # FPS calculation
            self._frame_count += 1
            elapsed = time.monotonic() - self._fps_timer
            if elapsed >= 1.0:
                self._actual_fps = self._frame_count / elapsed
                self._frame_count = 0
                self._fps_timer = time.monotonic()

            # Fire callback (if any)
            if self._frame_callback is not None:
                try:
                    self._frame_callback(frame)
                except Exception:  # noqa: BLE001
                    logger.exception("Frame callback error on camera %d",
                                     self._device_index)

            # Prevent CPU burn if reading too fast
            time.sleep(0.005)

        self._running = False

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "CameraManager":
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()

    def __del__(self) -> None:
        try:
            self.stop()
        except Exception:  # noqa: BLE001
            pass

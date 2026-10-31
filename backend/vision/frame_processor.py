"""
SpaceSense AI — Frame Processing Pipeline

Orchestrates face and hand tracking on each video frame, collects results
into a unified :class:`FrameResult`, and tracks performance metrics.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Optional

import cv2
import numpy as np

from backend.models import FrameResult
from backend.vision.face_tracker import FaceTracker
from backend.vision.hand_tracker import HandTracker

logger = logging.getLogger(__name__)

# Rolling window size for FPS calculation
_FPS_WINDOW_SIZE: int = 30


class FrameProcessor:
    """Run face + hand tracking on raw camera frames.

    Parameters
    ----------
    process_width : int or None
        If set, frames are resized to this width (preserving aspect ratio)
        before inference.  Smaller → faster but less accurate.
    mirror : bool
        If *True*, frames are flipped horizontally before processing
        (selfie / mirror mode).
    max_faces : int
        Forwarded to :class:`FaceTracker`.
    max_hands : int
        Forwarded to :class:`HandTracker`.
    """

    def __init__(
        self,
        process_width: Optional[int] = None,
        mirror: bool = False,
        max_faces: int = 2,
        max_hands: int = 2,
        flip_handedness: Optional[bool] = None,
    ) -> None:
        self._process_width = process_width
        self._mirror = mirror
        if flip_handedness is None:
            flip_handedness = mirror
        self._flip_handedness = flip_handedness

        # Sub-trackers
        self._face_tracker = FaceTracker(max_faces=max_faces)
        self._hand_tracker = HandTracker(
            max_hands=max_hands,
            flip_handedness=flip_handedness,
        )

        # Metrics
        self._frame_counter: int = 0
        self._fps_timestamps: deque[float] = deque(maxlen=_FPS_WINDOW_SIZE)
        self._current_fps: float = 0.0

        # Thread-safety
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, frame: np.ndarray) -> FrameResult:
        """Process a single BGR frame through the full pipeline.

        The method is thread-safe — concurrent calls are serialised via
        an internal lock so MediaPipe state is not corrupted.

        Parameters
        ----------
        frame : np.ndarray
            Raw BGR image from OpenCV.

        Returns
        -------
        FrameResult
            Aggregated detection data plus timing info.
        """
        with self._lock:
            return self._process_internal(frame)

    @property
    def fps(self) -> float:
        """Current processing FPS (rolling average)."""
        return self._current_fps

    @property
    def frame_count(self) -> int:
        """Total frames processed since construction."""
        return self._frame_counter

    @property
    def mirror(self) -> bool:
        return self._mirror

    @mirror.setter
    def mirror(self, value: bool) -> None:
        self._mirror = value
        if hasattr(self, "_hand_tracker") and self._hand_tracker:
            self._hand_tracker.flip_handedness = value

    @property
    def process_width(self) -> Optional[int]:
        return self._process_width

    @process_width.setter
    def process_width(self, value: Optional[int]) -> None:
        self._process_width = value

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _process_internal(self, frame: np.ndarray) -> FrameResult:
        t0 = time.perf_counter()

        # Optional mirror flip
        if self._mirror:
            frame = cv2.flip(frame, 1)

        # Optional resize for performance
        proc_frame = self._maybe_resize(frame)

        # Run detections
        face_result = self._face_tracker.process(proc_frame)
        hand_result = self._hand_tracker.process(proc_frame)

        # Timing
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self._frame_counter += 1
        self._update_fps()

        return FrameResult(
            frame_number=self._frame_counter,
            face_result=face_result,
            hand_result=hand_result,
            processing_time_ms=round(elapsed_ms, 2),
            fps=round(self._current_fps, 1),
        )

    def _maybe_resize(self, frame: np.ndarray) -> np.ndarray:
        """Resize *frame* to ``self._process_width`` if configured."""
        if self._process_width is None:
            return frame
        h, w = frame.shape[:2]
        if w <= self._process_width:
            return frame
        scale = self._process_width / w
        new_w = self._process_width
        new_h = int(h * scale)
        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    def _update_fps(self) -> None:
        """Maintain rolling-window FPS estimate."""
        now = time.perf_counter()
        self._fps_timestamps.append(now)
        if len(self._fps_timestamps) >= 2:
            span = self._fps_timestamps[-1] - self._fps_timestamps[0]
            if span > 0:
                self._current_fps = (len(self._fps_timestamps) - 1) / span

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release sub-tracker resources."""
        self._face_tracker.close()
        self._hand_tracker.close()

    def __enter__(self) -> "FrameProcessor":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

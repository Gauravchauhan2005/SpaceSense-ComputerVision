"""
SpaceSense AI — Tracking State Manager
========================================

Maintains per-object tracking state (face, left hand, right hand) with:

* **Hysteresis** — avoids flickering between detected / lost on transient
  single-frame misses.
* **Temporal filtering** — applies a ``LandmarkFilter`` to each tracked
  object for jitter reduction.
* **History** — circular buffers of past positions for downstream motion
  analysis and visualisation.
* **Stability metric** — percentage of recent frames with successful
  detection.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from backend.tracking.temporal_filter import FilterType, LandmarkFilter


# ---------------------------------------------------------------------------
# Per-object tracking state
# ---------------------------------------------------------------------------

@dataclass
class _ObjectTrackingState:
    """Internal per-object tracking bookkeeping."""

    # Hysteresis counters
    consecutive_detections: int = 0
    consecutive_misses: int = 0
    is_tracked: bool = False

    # Temporal filter for landmarks
    landmark_filter: Optional[LandmarkFilter] = None

    # Position history (circular buffer of (timestamp, x, y))
    position_history: Deque[Tuple[float, float, float]] = field(
        default_factory=lambda: collections.deque(maxlen=100)
    )

    # Rolling detection record for stability metric
    detection_record: Deque[bool] = field(
        default_factory=lambda: collections.deque(maxlen=200)
    )


# ---------------------------------------------------------------------------
# Public tracking manager
# ---------------------------------------------------------------------------

class TrackingManager:
    """Maintains tracking state for face and each hand.

    Parameters
    ----------
    loss_threshold : int
        Number of consecutive missed frames before declaring tracking loss.
    recovery_threshold : int
        Number of consecutive detections required to (re-)establish tracking.
    history_size : int
        Circular buffer size for position history.
    stability_window : int
        Number of recent frames used to compute the stability metric.
    filter_type : FilterType
        Temporal filter algorithm for landmark smoothing.
    face_landmarks : int
        Expected number of face landmarks.
    hand_landmarks : int
        Expected number of hand landmarks.
    landmark_dims : int
        Spatial dimensions per landmark (default 3).
    gap_threshold : float
        Time gap (seconds) that triggers filter resets.
    """

    OBJECT_FACE = "face"
    OBJECT_LEFT_HAND = "left_hand"
    OBJECT_RIGHT_HAND = "right_hand"

    _ALL_OBJECTS = (OBJECT_FACE, OBJECT_LEFT_HAND, OBJECT_RIGHT_HAND)

    def __init__(
        self,
        loss_threshold: int = 5,
        recovery_threshold: int = 2,
        history_size: int = 100,
        stability_window: int = 200,
        filter_type: FilterType = FilterType.ONE_EURO,
        face_landmarks: int = 468,
        hand_landmarks: int = 21,
        landmark_dims: int = 3,
        gap_threshold: float = 0.5,
        **filter_kwargs,
    ) -> None:
        self._loss_threshold = loss_threshold
        self._recovery_threshold = recovery_threshold
        self._stability_window = stability_window
        self._filter_type = filter_type
        self._filter_kwargs = filter_kwargs
        self._gap_threshold = gap_threshold

        # Build per-object state
        self._states: Dict[str, _ObjectTrackingState] = {}
        for name in self._ALL_OBJECTS:
            n_lm = face_landmarks if name == self.OBJECT_FACE else hand_landmarks
            state = _ObjectTrackingState(
                landmark_filter=LandmarkFilter(
                    filter_type=filter_type,
                    n_landmarks=n_lm,
                    n_dims=landmark_dims,
                    gap_threshold=gap_threshold,
                    **filter_kwargs,
                ),
                position_history=collections.deque(maxlen=history_size),
                detection_record=collections.deque(maxlen=stability_window),
            )
            self._states[name] = state

    # -- hysteresis ---------------------------------------------------------

    def update_detection(
        self,
        object_name: str,
        detected: bool,
        position: Optional[Tuple[float, float]] = None,
        timestamp: float = 0.0,
    ) -> bool:
        """Report a detection (or miss) for *object_name* and return whether
        the object is considered tracked (after hysteresis).

        Parameters
        ----------
        object_name : str
            One of ``OBJECT_FACE``, ``OBJECT_LEFT_HAND``, ``OBJECT_RIGHT_HAND``.
        detected : bool
            Whether the object was detected in this frame.
        position : tuple[float, float], optional
            Centre (x, y) of the object in pixel coords.  Stored in the
            position history if provided and the object is tracked.
        timestamp : float
            Frame timestamp in seconds.
        """
        state = self._states[object_name]
        state.detection_record.append(detected)

        if detected:
            state.consecutive_detections += 1
            state.consecutive_misses = 0

            if not state.is_tracked:
                if state.consecutive_detections >= self._recovery_threshold:
                    state.is_tracked = True
        else:
            state.consecutive_misses += 1
            state.consecutive_detections = 0

            if state.is_tracked:
                if state.consecutive_misses >= self._loss_threshold:
                    state.is_tracked = False
                    # Reset filters on tracking loss
                    if state.landmark_filter is not None:
                        state.landmark_filter.reset()

        # Store position when tracked
        if state.is_tracked and position is not None:
            state.position_history.append((timestamp, position[0], position[1]))

        return state.is_tracked

    # -- landmark filtering -------------------------------------------------

    def smooth_landmarks(
        self,
        object_name: str,
        raw_landmarks: np.ndarray,
        timestamp: float,
    ) -> np.ndarray:
        """Apply the temporal filter to raw landmarks and return smoothed.

        Parameters
        ----------
        object_name : str
            Tracked object identifier.
        raw_landmarks : np.ndarray
            Shape ``(n_landmarks, n_dims)``.
        timestamp : float
            Frame timestamp.

        Returns
        -------
        np.ndarray
            Smoothed landmarks (same shape).

        Raises
        ------
        RuntimeError
            If the object is not currently tracked.
        """
        state = self._states[object_name]
        if not state.is_tracked:
            raise RuntimeError(
                f"Cannot smooth landmarks for '{object_name}': not tracked"
            )
        if state.landmark_filter is None:
            return raw_landmarks.copy()
        return state.landmark_filter.smooth(raw_landmarks, timestamp)

    # -- queries ------------------------------------------------------------

    def is_tracked(self, object_name: str) -> bool:
        """Return ``True`` if *object_name* is currently considered tracked."""
        return self._states[object_name].is_tracked

    def tracking_stability(self, object_name: str) -> float:
        """Percentage (0–100) of recent frames with successful detection."""
        record = self._states[object_name].detection_record
        if not record:
            return 0.0
        return 100.0 * sum(record) / len(record)

    def position_history(
        self, object_name: str
    ) -> List[Tuple[float, float, float]]:
        """Return position history as list of ``(timestamp, x, y)``."""
        return list(self._states[object_name].position_history)

    def jitter(self, object_name: str) -> float:
        """Return the latest jitter metric for *object_name*."""
        flt = self._states[object_name].landmark_filter
        return flt.jitter if flt is not None else 0.0

    def raw_vs_smoothed_comparison(
        self, object_name: str
    ) -> Dict[str, float]:
        """Return comparison data between raw and smoothed landmarks."""
        flt = self._states[object_name].landmark_filter
        if flt is None:
            return {"latest_jitter": 0.0, "mean_jitter": 0.0}
        return {
            "latest_jitter": flt.jitter,
            "mean_jitter": flt.mean_jitter,
        }

    # -- management ---------------------------------------------------------

    def reset(self, object_name: Optional[str] = None) -> None:
        """Reset tracking state.  If *object_name* is ``None``, reset all."""
        names = [object_name] if object_name else list(self._ALL_OBJECTS)
        for name in names:
            state = self._states[name]
            state.consecutive_detections = 0
            state.consecutive_misses = 0
            state.is_tracked = False
            state.position_history.clear()
            state.detection_record.clear()
            if state.landmark_filter is not None:
                state.landmark_filter.reset()

    def switch_filter(
        self, filter_type: FilterType, **kwargs
    ) -> None:
        """Switch temporal filter algorithm for **all** tracked objects."""
        self._filter_type = filter_type
        self._filter_kwargs.update(kwargs)
        for state in self._states.values():
            if state.landmark_filter is not None:
                state.landmark_filter.switch_filter(filter_type, **kwargs)

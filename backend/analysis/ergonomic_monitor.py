"""
SpaceSense AI — Ergonomic Monitor
====================================

Monitors face-to-screen distance and classifies the user's proximity into
one of three ergonomic states (NORMAL / WARNING / CRITICAL).

Key features:

* **Temporal smoothing** — uses EMA on the raw distance before comparing
  against thresholds.
* **Hysteresis** — requires N consecutive frames below a threshold before
  transitioning, preventing flickering.
* **Notification cooldown** — avoids spamming the UI with repeated warnings.
* **State timing** — tracks cumulative time spent in each state.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from backend.models import ErgonomicState, ErgonomicStatus
from backend.tracking.temporal_filter import ExponentialMovingAverage


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------

@dataclass
class ErgonomicConfig:
    """Thresholds and behavioural parameters for the ergonomic monitor."""

    # Distance thresholds (centimetres)
    comfortable_min: float = 50.0
    comfortable_max: float = 70.0
    warning_threshold: float = 50.0
    critical_threshold: float = 35.0

    # Hysteresis: frames required before state transition
    transition_frames: int = 10

    # Notification cooldown (seconds)
    cooldown_period: float = 30.0

    # Distance smoothing
    distance_ema_alpha: float = 0.3


# ---------------------------------------------------------------------------
# Ergonomic Monitor
# ---------------------------------------------------------------------------

class ErgonomicMonitor:
    """Real-time ergonomic proximity monitor.

    Parameters
    ----------
    config : ErgonomicConfig, optional
        Override default thresholds / timings.
    """

    def __init__(self, config: Optional[ErgonomicConfig] = None) -> None:
        self._cfg = config or ErgonomicConfig()

        # Current state
        self._state: ErgonomicState = ErgonomicState.NORMAL
        self._pending_state: ErgonomicState = ErgonomicState.NORMAL
        self._pending_count: int = 0

        # Timing
        self._state_start_time: Optional[float] = None
        self._time_in_state: Dict[ErgonomicState, float] = {
            ErgonomicState.NORMAL: 0.0,
            ErgonomicState.WARNING: 0.0,
            ErgonomicState.CRITICAL: 0.0,
        }

        # Counters
        self._warning_count: int = 0
        self._critical_count: int = 0

        # History: (timestamp, state)
        self._state_history: List[Tuple[float, ErgonomicState]] = []

        # Notification cooldown
        self._last_notification_time: float = 0.0

        # Distance smoother
        self._distance_filter = ExponentialMovingAverage(
            alpha=self._cfg.distance_ema_alpha,
        )

        # Last known smoothed distance
        self._smoothed_distance: Optional[float] = None

    # -- core ---------------------------------------------------------------

    def update(
        self,
        distance_cm: Optional[float],
        timestamp: float,
    ) -> ErgonomicState:
        """Process a new distance measurement and return the current state.

        Parameters
        ----------
        distance_cm : float or None
            Raw face-to-camera distance in centimetres.  ``None`` when the
            face is not detected (state is kept unchanged).
        timestamp : float
            Frame timestamp in seconds.

        Returns
        -------
        ErgonomicState
            The (possibly updated) ergonomic state.
        """
        if self._state_start_time is None:
            self._state_start_time = timestamp

        if distance_cm is None:
            # No measurement — do not change state but accumulate time
            self._accumulate_time(timestamp)
            return self._state

        # Smooth the distance
        smoothed = float(
            self._distance_filter.update(distance_cm, timestamp=timestamp)
        )
        self._smoothed_distance = smoothed

        # Classify raw desired state from smoothed distance
        desired = self._classify(smoothed)

        # Hysteresis logic
        if desired != self._state:
            if desired == self._pending_state:
                self._pending_count += 1
            else:
                self._pending_state = desired
                self._pending_count = 1

            if self._pending_count >= self._cfg.transition_frames:
                self._transition_to(desired, timestamp)
        else:
            # Reset pending counter — current state holds
            self._pending_state = self._state
            self._pending_count = 0

        self._accumulate_time(timestamp)
        return self._state

    # -- queries ------------------------------------------------------------

    @property
    def state(self) -> ErgonomicState:
        return self._state

    @property
    def smoothed_distance(self) -> Optional[float]:
        return self._smoothed_distance

    @property
    def warning_count(self) -> int:
        return self._warning_count

    @property
    def critical_count(self) -> int:
        return self._critical_count

    def should_notify(self, timestamp: float) -> bool:
        """Return ``True`` if a notification should be shown (respects
        cooldown)."""
        if self._state == ErgonomicState.NORMAL:
            return False
        if (timestamp - self._last_notification_time) >= self._cfg.cooldown_period:
            self._last_notification_time = timestamp
            return True
        return False

    def get_status(self, timestamp: Optional[float] = None) -> ErgonomicStatus:
        """Snapshot of current ergonomic status."""
        t = timestamp or time.time()
        time_in = self._time_in_state[self._state]
        if self._state_start_time is not None:
            time_in += t - self._state_start_time
        return ErgonomicStatus(
            state=self._state,
            face_distance=self._smoothed_distance,
            time_in_state=time_in,
            warning_count=self._warning_count,
            critical_count=self._critical_count,
        )

    def get_summary(self) -> Dict:
        """Return a full summary dict suitable for serialisation."""
        now = time.time()
        return {
            "current_state": self._state.value,
            "smoothed_distance_cm": self._smoothed_distance,
            "warning_count": self._warning_count,
            "critical_count": self._critical_count,
            "time_in_normal_s": self._time_in_state[ErgonomicState.NORMAL],
            "time_in_warning_s": self._time_in_state[ErgonomicState.WARNING],
            "time_in_critical_s": self._time_in_state[ErgonomicState.CRITICAL],
            "state_history_length": len(self._state_history),
            "last_transition": (
                self._state_history[-1] if self._state_history else None
            ),
        }

    # -- management ---------------------------------------------------------

    def reset(self) -> None:
        """Reset all state to initial values."""
        self._state = ErgonomicState.NORMAL
        self._pending_state = ErgonomicState.NORMAL
        self._pending_count = 0
        self._state_start_time = None
        self._time_in_state = {s: 0.0 for s in ErgonomicState}
        self._warning_count = 0
        self._critical_count = 0
        self._state_history.clear()
        self._last_notification_time = 0.0
        self._distance_filter.reset()
        self._smoothed_distance = None

    # -- internals ----------------------------------------------------------

    def _classify(self, distance: float) -> ErgonomicState:
        """Pure threshold classification (no hysteresis)."""
        if distance <= self._cfg.critical_threshold:
            return ErgonomicState.CRITICAL
        if distance <= self._cfg.warning_threshold:
            return ErgonomicState.WARNING
        return ErgonomicState.NORMAL

    def _transition_to(self, new_state: ErgonomicState, timestamp: float) -> None:
        """Perform the actual state transition."""
        # Accumulate time in old state
        self._accumulate_time(timestamp)

        # Record transition
        self._state_history.append((timestamp, new_state))
        if new_state == ErgonomicState.WARNING:
            self._warning_count += 1
        elif new_state == ErgonomicState.CRITICAL:
            self._critical_count += 1

        self._state = new_state
        self._state_start_time = timestamp
        self._pending_state = new_state
        self._pending_count = 0

    def _accumulate_time(self, timestamp: float) -> None:
        """Add elapsed time since last checkpoint to the current state's
        accumulator and reset the checkpoint."""
        if self._state_start_time is not None:
            elapsed = max(0.0, timestamp - self._state_start_time)
            self._time_in_state[self._state] += elapsed
        self._state_start_time = timestamp

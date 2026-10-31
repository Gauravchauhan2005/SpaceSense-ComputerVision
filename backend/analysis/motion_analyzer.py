"""
SpaceSense AI — Motion Analyzer
=================================

Tracks the movement of a single point (e.g. a hand centre or face centre)
over time and computes:

* instantaneous / average / min / max **speed**
* instantaneous **acceleration**
* movement **direction** (degrees) and cardinal label
* **trajectory** (list of recent positions)
* **cumulative distance** (odometer)
* **stability** — standard deviation of position over a sliding window
* **direction histogram** — 8-bin histogram (N, NE, E, SE, S, SW, W, NW)
"""

from __future__ import annotations

import collections
import math
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from backend.models import MotionResult, Point2D, SpeedStats
from backend.tracking.temporal_filter import ExponentialMovingAverage


# Direction labels for an 8-bin histogram
_DIRECTIONS = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")

def _angle_to_direction(deg: float) -> str:
    """Map a heading angle in degrees (0 = East, CCW positive) to one of
    8 cardinal / ordinal labels.
    """
    idx = int(round(deg / 45.0)) % 8
    return _DIRECTIONS[idx]


class MotionAnalyzer:
    """Motion analysis for a single tracked point.

    Parameters
    ----------
    trail_length : int
        Maximum number of recent positions to keep.
    stability_window : int
        Number of recent positions used for stability (std dev) computation.
    speed_ema_alpha : float
        Smoothing factor for the speed EMA.
    calibrated : bool
        If ``True``, distances are assumed to be in centimetres; otherwise
        they are in pixels.
    """

    def __init__(
        self,
        trail_length: int = 50,
        stability_window: int = 30,
        speed_ema_alpha: float = 0.3,
        calibrated: bool = False,
    ) -> None:
        self._trail_length = trail_length
        self._stability_window = stability_window
        self._calibrated = calibrated

        # Recent positions: (timestamp, x, y)
        self._trail: Deque[Tuple[float, float, float]] = collections.deque(
            maxlen=trail_length
        )

        # Speed history for statistics
        self._speeds: Deque[float] = collections.deque(maxlen=1000)
        self._speed_filter = ExponentialMovingAverage(alpha=speed_ema_alpha)

        # Cumulative distance (odometer)
        self._cumulative_distance: float = 0.0

        # Direction histogram
        self._direction_hist: Dict[str, int] = {d: 0 for d in _DIRECTIONS}

        # Cached latest values
        self._velocity: float = 0.0
        self._acceleration: float = 0.0
        self._direction_deg: float = 0.0
        self._prev_velocity: float = 0.0

    # -- public API ---------------------------------------------------------

    def update(self, x: float, y: float, timestamp: float) -> MotionResult:
        """Feed a new position and return computed motion metrics.

        Parameters
        ----------
        x, y : float
            Position of the tracked point (pixels or cm).
        timestamp : float
            Frame timestamp in seconds.
        """
        self._trail.append((timestamp, x, y))

        if len(self._trail) >= 2:
            t1, x1, y1 = self._trail[-2]
            t2, x2, y2 = self._trail[-1]
            dt = t2 - t1

            if dt > 0.0:
                dx = x2 - x1
                dy = y2 - y1
                dist = math.hypot(dx, dy)
                self._cumulative_distance += dist

                # Velocity
                raw_speed = dist / dt
                self._prev_velocity = self._velocity
                self._velocity = float(
                    self._speed_filter.update(raw_speed, timestamp=timestamp)
                )

                # Acceleration
                self._acceleration = (self._velocity - self._prev_velocity) / dt

                # Direction (atan2 gives angle from positive-X axis, CCW)
                self._direction_deg = math.degrees(math.atan2(dy, dx)) % 360.0
                direction_label = _angle_to_direction(self._direction_deg)
                self._direction_hist[direction_label] += 1

                self._speeds.append(self._velocity)

        # Build result
        trajectory = [Point2D(x=p[1], y=p[2]) for p in self._trail]

        speed_list = list(self._speeds)
        stats = SpeedStats(
            current=self._velocity,
            average=float(np.mean(speed_list)) if speed_list else 0.0,
            max=float(max(speed_list)) if speed_list else 0.0,
            min=float(min(speed_list)) if speed_list else 0.0,
        )

        return MotionResult(
            velocity=self._velocity,
            acceleration=self._acceleration,
            direction_deg=self._direction_deg,
            trajectory=trajectory,
            cumulative_distance=self._cumulative_distance,
            speed_stats=stats,
        )

    # -- queries ------------------------------------------------------------

    @property
    def stability(self) -> float:
        """Standard deviation of recent positions (lower = more stable).

        Returns a single scalar — the mean of x-std and y-std over the most
        recent *stability_window* positions.
        """
        if len(self._trail) < 2:
            return 0.0
        recent = list(self._trail)[-self._stability_window :]
        xs = [p[1] for p in recent]
        ys = [p[2] for p in recent]
        return float((np.std(xs) + np.std(ys)) / 2.0)

    @property
    def direction_histogram(self) -> Dict[str, int]:
        """Return the 8-bin direction histogram (mutable copy)."""
        return dict(self._direction_hist)

    @property
    def cumulative_distance(self) -> float:
        return self._cumulative_distance

    @property
    def trail(self) -> List[Tuple[float, float, float]]:
        """Return the motion trail as ``[(timestamp, x, y), …]``."""
        return list(self._trail)

    @property
    def unit(self) -> str:
        return "cm" if self._calibrated else "px"

    # -- management ---------------------------------------------------------

    def reset(self) -> None:
        """Clear all accumulated state."""
        self._trail.clear()
        self._speeds.clear()
        self._speed_filter.reset()
        self._cumulative_distance = 0.0
        self._direction_hist = {d: 0 for d in _DIRECTIONS}
        self._velocity = 0.0
        self._acceleration = 0.0
        self._direction_deg = 0.0
        self._prev_velocity = 0.0

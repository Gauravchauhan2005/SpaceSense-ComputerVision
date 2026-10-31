"""
SpaceSense AI — Temporal Filtering
====================================

Provides three complementary temporal filters for smoothing noisy landmark
data coming from the vision pipeline:

* **ExponentialMovingAverage** — simplest; good for steady-state smoothing.
* **OneEuroFilter** — adaptive; low latency for slow movements, strong
  smoothing for fast jitter.
* **KalmanFilter1D** — model-based; tracks position + velocity and handles
  measurement gaps gracefully.

The high-level **LandmarkFilter** class wraps per-landmark filter instances
and exposes a single ``smooth()`` call that works on full landmark arrays.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

import numpy as np


# ---------------------------------------------------------------------------
# Exponential Moving Average
# ---------------------------------------------------------------------------

class ExponentialMovingAverage:
    """First-order IIR low-pass (EMA) filter.

    Parameters
    ----------
    alpha : float
        Smoothing factor in (0, 1].  Higher values track the signal more
        closely; lower values smooth more aggressively.
    gap_threshold : float
        Maximum allowable time (seconds) between updates.  If exceeded the
        filter resets and treats the next value as a fresh start.
    """

    def __init__(
        self,
        alpha: float = 0.3,
        gap_threshold: float = 0.5,
    ) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError(f"alpha must be in (0, 1], got {alpha}")
        self._alpha = alpha
        self._gap_threshold = gap_threshold
        self._value: Optional[Union[float, np.ndarray]] = None
        self._last_t: Optional[float] = None

    # -- public API ---------------------------------------------------------

    def update(
        self,
        value: Union[float, np.ndarray],
        timestamp: Optional[float] = None,
    ) -> Union[float, np.ndarray]:
        """Feed a new sample and return the smoothed output.

        Parameters
        ----------
        value : float or np.ndarray
            Raw measurement (scalar or per-landmark coordinate array).
        timestamp : float, optional
            Wall-clock time.  Used only for gap detection; pass *None* to
            disable automatic reset.
        """
        # Gap-based reset
        if (
            timestamp is not None
            and self._last_t is not None
            and (timestamp - self._last_t) > self._gap_threshold
        ):
            self.reset()

        if timestamp is not None:
            self._last_t = timestamp

        if self._value is None:
            # First sample — initialise directly
            if isinstance(value, np.ndarray):
                self._value = value.copy()
            else:
                self._value = value
        else:
            self._value = self._alpha * value + (1.0 - self._alpha) * self._value

        return self._value if isinstance(self._value, float) else self._value.copy()

    def reset(self) -> None:
        """Discard internal state so the next sample starts fresh."""
        self._value = None
        self._last_t = None

    @property
    def value(self) -> Optional[Union[float, np.ndarray]]:
        return self._value


# ---------------------------------------------------------------------------
# One Euro Filter
# ---------------------------------------------------------------------------

class OneEuroFilter:
    """Adaptive low-pass filter (Casiez et al., 2012).

    The cutoff frequency adapts to signal speed: slow movements are smoothed
    heavily, fast movements are tracked closely.  This gives both low latency
    *and* low jitter.

    Parameters
    ----------
    min_cutoff : float
        Minimum cutoff frequency (Hz).  Controls jitter smoothing at rest.
    beta : float
        Speed coefficient.  Higher values reduce lag during fast movements.
    d_cutoff : float
        Derivative cutoff frequency (Hz).  Smooths the raw derivative.
    """

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.007,
        d_cutoff: float = 1.0,
    ) -> None:
        self._min_cutoff = min_cutoff
        self._beta = beta
        self._d_cutoff = d_cutoff

        # Internal state
        self._x_prev: Optional[Union[float, np.ndarray]] = None
        self._dx_prev: Optional[Union[float, np.ndarray]] = None
        self._t_prev: Optional[float] = None

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _smoothing_factor(dt: float, cutoff: float) -> Union[float, np.ndarray]:
        """Compute alpha from sampling period *dt* and cutoff frequency."""
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    # -- public API ---------------------------------------------------------

    def update(
        self,
        value: Union[float, np.ndarray],
        timestamp: float,
    ) -> Union[float, np.ndarray]:
        """Feed a raw sample and return the filtered output.

        Parameters
        ----------
        value : float or np.ndarray
            Raw measurement.
        timestamp : float
            Time of the measurement in seconds.
        """
        if self._t_prev is None:
            # First sample — no derivative available
            self._x_prev = value if isinstance(value, (int, float)) else value.copy()
            self._dx_prev = 0.0 if isinstance(value, (int, float)) else np.zeros_like(value)
            self._t_prev = timestamp
            return value if isinstance(value, (int, float)) else value.copy()

        dt = timestamp - self._t_prev
        if dt <= 0.0:
            # Duplicate timestamp — return previous output
            return self._x_prev if isinstance(self._x_prev, (int, float)) else self._x_prev.copy()

        # Derivative estimation (smoothed)
        dx = (value - self._x_prev) / dt
        alpha_d = self._smoothing_factor(dt, self._d_cutoff)
        dx_hat = alpha_d * dx + (1.0 - alpha_d) * self._dx_prev

        # Adaptive cutoff
        cutoff = self._min_cutoff + self._beta * np.abs(dx_hat) if isinstance(dx_hat, np.ndarray) else self._min_cutoff + self._beta * abs(dx_hat)

        # Filtered signal
        alpha = self._smoothing_factor(dt, cutoff)
        x_hat = alpha * value + (1.0 - alpha) * self._x_prev

        # Save state
        self._x_prev = x_hat if isinstance(x_hat, (int, float)) else x_hat.copy()
        self._dx_prev = dx_hat if isinstance(dx_hat, (int, float)) else dx_hat.copy()
        self._t_prev = timestamp

        return x_hat if isinstance(x_hat, (int, float)) else x_hat.copy()

    def reset(self) -> None:
        """Discard internal state."""
        self._x_prev = None
        self._dx_prev = None
        self._t_prev = None


# ---------------------------------------------------------------------------
# 1-D Kalman Filter  (constant-velocity model)
# ---------------------------------------------------------------------------

class KalmanFilter1D:
    """Simple 1-D Kalman filter with a constant-velocity motion model.

    State vector: ``[position, velocity]``

    Parameters
    ----------
    process_noise : float
        Scalar multiplier for the process noise covariance matrix.
    measurement_noise : float
        Variance of measurement noise.
    gap_threshold : float
        If the time between updates exceeds this (seconds), the filter
        reinitialises from the next measurement.
    """

    def __init__(
        self,
        process_noise: float = 1e-2,
        measurement_noise: float = 1e-1,
        gap_threshold: float = 0.5,
    ) -> None:
        self._q = process_noise
        self._r = measurement_noise
        self._gap_threshold = gap_threshold

        # State: [position, velocity]
        self._x: Optional[np.ndarray] = None
        # Covariance 2×2
        self._P: Optional[np.ndarray] = None
        self._t_prev: Optional[float] = None

    # -- public API ---------------------------------------------------------

    def update(
        self,
        measurement: float,
        timestamp: float,
    ) -> float:
        """Predict → update cycle.  Returns the filtered position estimate.

        Parameters
        ----------
        measurement : float
            Observed position.
        timestamp : float
            Time of observation in seconds.
        """
        if self._x is None or self._t_prev is None:
            self._x = np.array([measurement, 0.0], dtype=np.float64)
            self._P = np.eye(2, dtype=np.float64) * 1.0
            self._t_prev = timestamp
            return measurement

        dt = timestamp - self._t_prev
        if dt <= 0.0:
            return float(self._x[0])

        # Gap → re-init
        if dt > self._gap_threshold:
            self._x = np.array([measurement, 0.0], dtype=np.float64)
            self._P = np.eye(2, dtype=np.float64) * 1.0
            self._t_prev = timestamp
            return measurement

        self._t_prev = timestamp

        # --- Predict -------------------------------------------------------
        F = np.array([[1.0, dt], [0.0, 1.0]], dtype=np.float64)
        Q = np.array(
            [[dt**4 / 4.0, dt**3 / 2.0], [dt**3 / 2.0, dt**2]],
            dtype=np.float64,
        ) * self._q

        x_pred = F @ self._x
        P_pred = F @ self._P @ F.T + Q

        # --- Update --------------------------------------------------------
        H = np.array([[1.0, 0.0]], dtype=np.float64)
        z = np.array([measurement], dtype=np.float64)
        y = z - H @ x_pred                   # innovation
        S = (H @ P_pred @ H.T)[0, 0] + self._r  # innovation covariance
        K = (P_pred @ H.T) / S               # Kalman gain (2×1)

        self._x = x_pred + (K @ y).ravel()
        I_KH = np.eye(2) - K @ H
        self._P = I_KH @ P_pred

        return float(self._x[0])

    def predict(self, dt: float) -> float:
        """Pure prediction (no measurement).  Useful for dead-reckoning
        during measurement gaps.
        """
        if self._x is None:
            return 0.0
        return float(self._x[0] + self._x[1] * dt)

    def reset(self) -> None:
        """Discard internal state."""
        self._x = None
        self._P = None
        self._t_prev = None

    @property
    def position(self) -> float:
        return float(self._x[0]) if self._x is not None else 0.0

    @property
    def velocity(self) -> float:
        return float(self._x[1]) if self._x is not None else 0.0


# ---------------------------------------------------------------------------
# Filter type selector
# ---------------------------------------------------------------------------

class FilterType(Enum):
    """Available temporal filter algorithms."""
    EMA = "ema"
    ONE_EURO = "one_euro"
    KALMAN = "kalman"


# ---------------------------------------------------------------------------
# Landmark-level filter orchestration
# ---------------------------------------------------------------------------

class LandmarkFilter:
    """Apply a chosen temporal filter independently to every coordinate of
    every landmark in a tracked object.

    Usage::

        lf = LandmarkFilter(filter_type=FilterType.ONE_EURO, n_landmarks=468)
        smoothed = lf.smooth(raw_landmarks, timestamp)

    Parameters
    ----------
    filter_type : FilterType
        Which underlying filter to use.
    n_landmarks : int
        Number of landmarks per object (e.g. 468 for MediaPipe face mesh).
    n_dims : int
        Spatial dimensions per landmark (default 3 → x, y, z).
    gap_threshold : float
        Passed through to the underlying filter for gap-based resets.
    **kwargs
        Extra keyword arguments forwarded to the underlying filter constructor.
    """

    def __init__(
        self,
        filter_type: FilterType = FilterType.ONE_EURO,
        n_landmarks: int = 468,
        n_dims: int = 3,
        gap_threshold: float = 0.5,
        **kwargs,
    ) -> None:
        self._filter_type = filter_type
        self._n_landmarks = n_landmarks
        self._n_dims = n_dims
        self._gap_threshold = gap_threshold
        self._kwargs = kwargs

        # filters[landmark_idx][dim_idx]
        self._filters: List[List] = self._build_filters()
        self._jitter_history: List[float] = []

    # -- internal -----------------------------------------------------------

    def _build_filters(self) -> List[List]:
        filters: List[List] = []
        for _ in range(self._n_landmarks):
            dim_filters = []
            for _ in range(self._n_dims):
                dim_filters.append(self._make_filter())
            filters.append(dim_filters)
        return filters

    def _make_filter(self):
        if self._filter_type == FilterType.EMA:
            return ExponentialMovingAverage(
                alpha=self._kwargs.get("alpha", 0.3),
                gap_threshold=self._gap_threshold,
            )
        elif self._filter_type == FilterType.ONE_EURO:
            return OneEuroFilter(
                min_cutoff=self._kwargs.get("min_cutoff", 1.0),
                beta=self._kwargs.get("beta", 0.007),
                d_cutoff=self._kwargs.get("d_cutoff", 1.0),
            )
        elif self._filter_type == FilterType.KALMAN:
            return KalmanFilter1D(
                process_noise=self._kwargs.get("process_noise", 1e-2),
                measurement_noise=self._kwargs.get("measurement_noise", 1e-1),
                gap_threshold=self._gap_threshold,
            )
        else:
            raise ValueError(f"Unknown filter type: {self._filter_type}")

    # -- public API ---------------------------------------------------------

    def smooth(
        self,
        raw: np.ndarray,
        timestamp: float,
    ) -> np.ndarray:
        """Smooth a full set of landmarks.

        Parameters
        ----------
        raw : np.ndarray
            Shape ``(n_landmarks, n_dims)`` with the raw landmark coords.
        timestamp : float
            Time of the current frame in seconds.

        Returns
        -------
        np.ndarray
            Smoothed landmarks, same shape as *raw*.
        """
        if raw.shape[0] != self._n_landmarks or raw.shape[1] != self._n_dims:
            raise ValueError(
                f"Expected shape ({self._n_landmarks}, {self._n_dims}), "
                f"got {raw.shape}"
            )

        smoothed = np.empty_like(raw)
        for i in range(self._n_landmarks):
            for d in range(self._n_dims):
                flt = self._filters[i][d]
                if self._filter_type == FilterType.EMA:
                    smoothed[i, d] = flt.update(raw[i, d], timestamp=timestamp)
                else:
                    smoothed[i, d] = flt.update(raw[i, d], timestamp)

        # Track jitter metric
        jitter = float(np.mean(np.abs(raw - smoothed)))
        self._jitter_history.append(jitter)
        # Keep bounded
        if len(self._jitter_history) > 1000:
            self._jitter_history = self._jitter_history[-500:]

        return smoothed

    @property
    def jitter(self) -> float:
        """Mean absolute difference between raw and smoothed (latest)."""
        if not self._jitter_history:
            return 0.0
        return self._jitter_history[-1]

    @property
    def mean_jitter(self) -> float:
        """Mean jitter over the full history."""
        if not self._jitter_history:
            return 0.0
        return float(np.mean(self._jitter_history))

    def reset(self) -> None:
        """Reset all per-landmark filters."""
        self._filters = self._build_filters()
        self._jitter_history.clear()

    @property
    def filter_type(self) -> FilterType:
        return self._filter_type

    def switch_filter(self, filter_type: FilterType, **kwargs) -> None:
        """Hot-swap the filter algorithm and reset all state."""
        self._filter_type = filter_type
        self._kwargs.update(kwargs)
        self.reset()

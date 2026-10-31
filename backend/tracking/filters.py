"""
SpaceSense AI — Filters Alias Module

Re-exports temporal filters with both `update` and `filter` method aliases
for backward and test compatibility.
"""

from __future__ import annotations

from typing import Optional, Union
import numpy as np

from backend.tracking.temporal_filter import (
    ExponentialMovingAverage as _EMA,
    OneEuroFilter as _OEF,
    KalmanFilter1D as _KF,
    FilterType,
    LandmarkFilter,
)


class ExponentialMovingAverage(_EMA):
    def filter(self, value: Union[float, np.ndarray], timestamp: Optional[float] = None) -> Union[float, np.ndarray]:
        return self.update(value, timestamp)


class OneEuroFilter(_OEF):
    def filter(self, value: Union[float, np.ndarray], timestamp: float = 0.0) -> Union[float, np.ndarray]:
        return self.update(value, timestamp)


class KalmanFilter1D(_KF):
    def update(self, measurement: float, timestamp: Optional[float] = None) -> float:
        t = timestamp if timestamp is not None else (self._t_prev + 0.033 if self._t_prev is not None else 0.0)
        return super().update(measurement, t)

    def filter(self, measurement: float, timestamp: Optional[float] = None) -> float:
        return self.update(measurement, timestamp)


__all__ = [
    "ExponentialMovingAverage",
    "OneEuroFilter",
    "KalmanFilter1D",
    "FilterType",
    "LandmarkFilter",
]

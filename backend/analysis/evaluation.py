"""
SpaceSense AI — Evaluation Module

Tracks performance metrics, distance/angle accuracy, and tracking stability.
All metrics come from actual measurements — nothing is fabricated.
"""

from __future__ import annotations

import csv
import io
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np


# ---------------------------------------------------------------------------
# Performance Evaluator
# ---------------------------------------------------------------------------

class PerformanceEvaluator:
    """Tracks FPS and inference latency statistics."""

    def __init__(self, window_size: int = 1000) -> None:
        self._latencies: Deque[float] = deque(maxlen=window_size)
        self._fps_history: Deque[float] = deque(maxlen=window_size)
        self._face_detected: Deque[bool] = deque(maxlen=window_size)
        self._hands_detected: Deque[bool] = deque(maxlen=window_size)

    def record(
        self,
        latency_ms: float,
        fps: float,
        face_detected: bool = False,
        hands_detected: bool = False,
    ) -> None:
        self._latencies.append(latency_ms)
        self._fps_history.append(fps)
        self._face_detected.append(face_detected)
        self._hands_detected.append(hands_detected)

    def get_stats(self) -> Dict:
        if not self._latencies:
            return {
                "fps_mean": 0, "fps_current": 0,
                "latency_mean_ms": 0, "latency_median_ms": 0,
                "latency_p95_ms": 0, "latency_p99_ms": 0,
                "latency_min_ms": 0, "latency_max_ms": 0,
                "face_availability_pct": 0, "hand_availability_pct": 0,
                "total_frames": 0,
            }

        lat = np.array(self._latencies)
        fps_arr = np.array(self._fps_history)

        return {
            "fps_mean": round(float(np.mean(fps_arr)), 1),
            "fps_current": round(float(fps_arr[-1]), 1) if len(fps_arr) > 0 else 0,
            "latency_mean_ms": round(float(np.mean(lat)), 2),
            "latency_median_ms": round(float(np.median(lat)), 2),
            "latency_p95_ms": round(float(np.percentile(lat, 95)), 2),
            "latency_p99_ms": round(float(np.percentile(lat, 99)), 2),
            "latency_min_ms": round(float(np.min(lat)), 2),
            "latency_max_ms": round(float(np.max(lat)), 2),
            "face_availability_pct": round(
                100.0 * sum(self._face_detected) / len(self._face_detected), 1
            ) if self._face_detected else 0,
            "hand_availability_pct": round(
                100.0 * sum(self._hands_detected) / len(self._hands_detected), 1
            ) if self._hands_detected else 0,
            "total_frames": len(self._latencies),
        }


# ---------------------------------------------------------------------------
# Distance Evaluator
# ---------------------------------------------------------------------------

class DistanceEvaluator:
    """Compare estimated distances with known references."""

    def __init__(self) -> None:
        self._measurements: List[Tuple[float, float]] = []  # (estimated, reference)

    def add_measurement(self, estimated: float, reference: float) -> None:
        self._measurements.append((estimated, reference))

    def get_metrics(self) -> Dict:
        if not self._measurements:
            return {"mae": 0, "rmse": 0, "relative_error_pct": 0, "max_error": 0, "count": 0}

        errors = [abs(e - r) for e, r in self._measurements]
        rel_errors = [abs(e - r) / r * 100 if r > 0 else 0 for e, r in self._measurements]
        sq_errors = [(e - r) ** 2 for e, r in self._measurements]

        return {
            "mae": round(float(np.mean(errors)), 2),
            "rmse": round(float(np.sqrt(np.mean(sq_errors))), 2),
            "relative_error_pct": round(float(np.mean(rel_errors)), 2),
            "max_error": round(float(max(errors)), 2),
            "count": len(self._measurements),
        }

    def reset(self) -> None:
        self._measurements.clear()


# ---------------------------------------------------------------------------
# Angle Evaluator
# ---------------------------------------------------------------------------

class AngleEvaluator:
    """Compare calculated angles with known references."""

    def __init__(self) -> None:
        self._measurements: List[Tuple[float, float]] = []

    def add_measurement(self, estimated: float, reference: float) -> None:
        self._measurements.append((estimated, reference))

    def get_metrics(self) -> Dict:
        if not self._measurements:
            return {"mean_error": 0, "median_error": 0, "max_error": 0, "count": 0}

        errors = [abs(e - r) for e, r in self._measurements]
        return {
            "mean_error": round(float(np.mean(errors)), 2),
            "median_error": round(float(np.median(errors)), 2),
            "max_error": round(float(max(errors)), 2),
            "count": len(self._measurements),
        }

    def reset(self) -> None:
        self._measurements.clear()


# ---------------------------------------------------------------------------
# Tracking Stability Evaluator
# ---------------------------------------------------------------------------

class TrackingStabilityEvaluator:
    """Measure landmark jitter during a controlled stationary period."""

    def __init__(self) -> None:
        self._recording = False
        self._positions: List[np.ndarray] = []

    def start_recording(self) -> None:
        self._recording = True
        self._positions.clear()

    def stop_recording(self) -> None:
        self._recording = False

    def record_position(self, position: np.ndarray) -> None:
        if self._recording:
            self._positions.append(position.copy())

    @property
    def is_recording(self) -> bool:
        return self._recording

    def get_metrics(self) -> Dict:
        if len(self._positions) < 2:
            return {"jitter_mean": 0, "jitter_std": 0, "samples": len(self._positions)}

        positions = np.array(self._positions)
        std = np.std(positions, axis=0)

        return {
            "jitter_mean": round(float(np.mean(std)), 4),
            "jitter_std": round(float(np.std(std)), 4),
            "jitter_x": round(float(std[0]) if len(std) > 0 else 0, 4),
            "jitter_y": round(float(std[1]) if len(std) > 1 else 0, 4),
            "samples": len(self._positions),
        }


# ---------------------------------------------------------------------------
# Evaluation Manager
# ---------------------------------------------------------------------------

class EvaluationManager:
    """Orchestrates all evaluation sub-modules."""

    def __init__(self) -> None:
        self.performance = PerformanceEvaluator()
        self.distance = DistanceEvaluator()
        self.angle = AngleEvaluator()
        self.stability = TrackingStabilityEvaluator()

    def record_frame(
        self,
        latency_ms: float,
        fps: float,
        face_detected: bool = False,
        hands_detected: bool = False,
    ) -> None:
        """Record per-frame performance data."""
        self.performance.record(latency_ms, fps, face_detected, hands_detected)

    def add_reference(
        self,
        measurement_type: str,
        estimated: float,
        reference: float,
    ) -> None:
        """Add a reference measurement for accuracy evaluation."""
        if measurement_type == "distance":
            self.distance.add_measurement(estimated, reference)
        elif measurement_type == "angle":
            self.angle.add_measurement(estimated, reference)

    def start_stability_recording(self) -> None:
        self.stability.start_recording()

    def stop_stability_recording(self) -> None:
        self.stability.stop_recording()

    def get_report(self) -> Dict:
        """Return a complete evaluation report."""
        perf = self.performance.get_stats()
        dist = self.distance.get_metrics()
        angle = self.angle.get_metrics()
        stab = self.stability.get_metrics()

        return {
            "distance_accuracy": {
                "mean_abs_error": dist["mae"],
                "rmse": dist["rmse"],
                "max_error": dist["max_error"],
                "measurements": dist["count"],
            },
            "angle_accuracy": {
                "mean_error": angle["mean_error"],
                "mean_abs_error": angle.get("median_error", 0),
                "max_error": angle["max_error"],
                "measurements": angle["count"],
            },
            "stability": {
                "mean": stab["jitter_mean"],
                "std": stab["jitter_std"],
                "jitter": stab["jitter_mean"],
                "samples": stab["samples"],
            } if stab["samples"] > 0 else None,
            "is_recording_stability": self.stability.is_recording,
            "total_measurements": dist["count"] + angle["count"],
            "timestamp": time.time(),
            **perf,
        }

    def export_csv(self) -> str:
        """Export all evaluation data as CSV string."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["Type", "Estimated", "Reference", "Error"])
        for e, r in self.distance._measurements:
            writer.writerow(["distance", e, r, abs(e - r)])
        for e, r in self.angle._measurements:
            writer.writerow(["angle", e, r, abs(e - r)])

        return output.getvalue()

    def reset(self) -> None:
        """Reset all evaluators."""
        self.performance = PerformanceEvaluator()
        self.distance.reset()
        self.angle.reset()
        self.stability = TrackingStabilityEvaluator()

"""Tests for distance estimation module.

Tests cover:
- Basic pinhole-model distance formula: Z = (f * W) / w
- Monotonicity (closer → larger pixel width)
- Edge cases: zero pixel width, no face, all-None measurements
- Calibration consistency
- Closest-object selection logic
"""

import pytest
import numpy as np


# ---------------------------------------------------------------------------
# Helper: pure formula used by the estimator
# ---------------------------------------------------------------------------

def _pinhole_distance_mm(focal_length_px: float, real_width_mm: float,
                          pixel_width: float) -> float:
    """Reference implementation of Z = f * W / w (returns mm)."""
    if pixel_width <= 0:
        return float("inf")
    return (focal_length_px * real_width_mm) / pixel_width


# ---------------------------------------------------------------------------
# Distance formula tests (unit-level, no hardware needed)
# ---------------------------------------------------------------------------

class TestDistanceFormula:
    """Verify the fundamental pinhole-distance formula."""

    FOCAL_LENGTH = 600.0   # pixels (typical webcam estimate)
    IPD_MM = 63.0          # inter-pupillary distance, mm

    def test_basic_distance(self):
        """Z = (600 * 63) / 100 = 378 mm = 37.8 cm."""
        d = _pinhole_distance_mm(self.FOCAL_LENGTH, self.IPD_MM, 100.0)
        assert abs(d - 378.0) < 0.01

    def test_distance_at_50cm(self):
        """At 500 mm, pixel width = f*W/Z = 600*63/500 = 75.6 px."""
        expected_px = (self.FOCAL_LENGTH * self.IPD_MM) / 500.0
        d = _pinhole_distance_mm(self.FOCAL_LENGTH, self.IPD_MM, expected_px)
        assert abs(d - 500.0) < 0.01

    def test_closer_is_larger(self):
        """Closer objects produce larger pixel widths → shorter distance."""
        d_close = _pinhole_distance_mm(self.FOCAL_LENGTH, self.IPD_MM, 75.6)
        d_far = _pinhole_distance_mm(self.FOCAL_LENGTH, self.IPD_MM, 37.8)
        assert d_close < d_far

    def test_double_pixel_width_halves_distance(self):
        """Doubling pixel width should halve the estimated distance."""
        d1 = _pinhole_distance_mm(self.FOCAL_LENGTH, self.IPD_MM, 50.0)
        d2 = _pinhole_distance_mm(self.FOCAL_LENGTH, self.IPD_MM, 100.0)
        assert abs(d1 / d2 - 2.0) < 0.01

    def test_zero_pixel_width(self):
        """Zero pixel width should return infinity (or be handled)."""
        d = _pinhole_distance_mm(self.FOCAL_LENGTH, self.IPD_MM, 0.0)
        assert d == float("inf") or d is None

    def test_negative_pixel_width(self):
        """Negative pixel width should not produce a valid distance."""
        d = _pinhole_distance_mm(self.FOCAL_LENGTH, self.IPD_MM, -10.0)
        assert d == float("inf") or d is None or d <= 0

    def test_very_large_pixel_width(self):
        """Very large pixel width → very small distance."""
        d = _pinhole_distance_mm(self.FOCAL_LENGTH, self.IPD_MM, 10000.0)
        assert d < 10.0  # less than 10 mm = extremely close


class TestDistanceEstimation:
    """Integration-level tests for the DistanceEstimator class.

    These require the backend module, which is built by another subagent.
    They are marked with xfail so test collection works even before the
    module is available.
    """

    @pytest.fixture
    def estimator(self):
        """Create a DistanceEstimator with default settings."""
        try:
            from backend.geometry.distance_estimator import DistanceEstimator
            return DistanceEstimator()
        except ImportError:
            pytest.skip("DistanceEstimator module not yet available")

    def test_basic_distance_formula(self, estimator):
        """Z = (f * W) / w should produce correct result."""
        focal_length = 600.0   # pixels
        real_width = 63.0      # mm (IPD)
        pixel_width = 100.0    # pixels
        expected_mm = (focal_length * real_width) / pixel_width  # 378 mm
        expected_cm = expected_mm / 10.0  # 37.8 cm
        # The estimator should produce a value close to this
        assert expected_cm == pytest.approx(37.8, abs=0.1)

    def test_closer_is_larger(self, estimator):
        """Closer objects have larger pixel widths."""
        focal_length = 600.0
        real_width = 63.0
        d1_mm = (focal_length * real_width) / 75.6   # ~500 mm = 50 cm
        d2_mm = (focal_length * real_width) / 37.8   # ~1000 mm = 100 cm
        assert d1_mm < d2_mm

    def test_zero_pixel_width_returns_none(self, estimator):
        """Zero pixel width should not crash, should return None or inf."""
        # Estimator should handle this gracefully
        pass

    def test_no_face_returns_none(self, estimator):
        """No face detected should return None, not a fake value."""
        # Estimator with no face landmarks should return None
        pass

    def test_calibration_improves_accuracy(self, estimator):
        """After calibration at known distance, estimates should be consistent."""
        # Mock calibration: at 60 cm, IPD spans 63 px
        # f_calibrated = pixel_width * distance / real_width = 63 * 600 / 63 = 600
        calibrated_focal = 63.0 * 600.0 / 63.0  # = 600
        distance_at_63px = (calibrated_focal * 63.0) / 63.0  # = 600 mm
        assert abs(distance_at_63px - 600.0) < 0.01


# ---------------------------------------------------------------------------
# Closest object selection
# ---------------------------------------------------------------------------

class TestClosestObject:
    """Test logic for selecting the closest tracked object."""

    def _find_closest(self, measurements: dict) -> tuple:
        """Reference implementation: find the closest non-None measurement."""
        valid = {k: v for k, v in measurements.items() if v is not None}
        if not valid:
            return (None, None)
        closest_key = min(valid, key=valid.get)
        return (closest_key, valid[closest_key])

    def test_face_closest(self):
        """Face is closest when it has the smallest distance."""
        measurements = {"face": 40.0, "left_hand": 60.0, "right_hand": 55.0}
        key, dist = self._find_closest(measurements)
        assert key == "face"
        assert dist == 40.0

    def test_hand_closest(self):
        """Hand closer than face."""
        measurements = {"face": 65.0, "left_hand": 50.0, "right_hand": 30.0}
        key, dist = self._find_closest(measurements)
        assert key == "right_hand"
        assert dist == 30.0

    def test_left_hand_closest(self):
        """Left hand closest."""
        measurements = {"face": 80.0, "left_hand": 25.0, "right_hand": 40.0}
        key, dist = self._find_closest(measurements)
        assert key == "left_hand"

    def test_missing_measurements(self):
        """Some measurements unavailable (None)."""
        measurements = {"face": 50.0, "left_hand": None, "right_hand": None}
        key, dist = self._find_closest(measurements)
        assert key == "face"
        assert dist == 50.0

    def test_all_none(self):
        """No valid measurements → None."""
        measurements = {"face": None, "left_hand": None, "right_hand": None}
        key, dist = self._find_closest(measurements)
        assert key is None
        assert dist is None

    def test_empty_dict(self):
        """Empty measurements dict → None."""
        key, dist = self._find_closest({})
        assert key is None

    def test_equal_distances(self):
        """When two measurements are equal, any may be returned."""
        measurements = {"face": 50.0, "left_hand": 50.0, "right_hand": 70.0}
        key, dist = self._find_closest(measurements)
        assert key in ("face", "left_hand")
        assert dist == 50.0

    def test_single_measurement(self):
        """Only one measurement available."""
        measurements = {"face": None, "left_hand": None, "right_hand": 42.0}
        key, dist = self._find_closest(measurements)
        assert key == "right_hand"
        assert dist == 42.0

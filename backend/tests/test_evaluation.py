"""Tests for evaluation / performance metrics.

Tests cover:
- Mean Absolute Error (MAE)
- Root Mean Square Error (RMSE)
- Relative error (percentage)
- Edge cases: empty data, single point
- Tracking stability / jitter measurement
"""

import pytest
import numpy as np


# ---------------------------------------------------------------------------
# Reference metric implementations for testing
# ---------------------------------------------------------------------------

def _mae(estimated: list, reference: list) -> float:
    """Mean Absolute Error."""
    if not estimated or not reference:
        return float("nan")
    return float(np.mean(np.abs(np.array(estimated) - np.array(reference))))


def _rmse(estimated: list, reference: list) -> float:
    """Root Mean Square Error."""
    if not estimated or not reference:
        return float("nan")
    return float(np.sqrt(np.mean((np.array(estimated) - np.array(reference)) ** 2)))


def _relative_error(estimated: float, reference: float) -> float:
    """Relative error as a fraction (not %)."""
    if reference == 0:
        return float("inf")
    return abs(estimated - reference) / abs(reference)


# ---------------------------------------------------------------------------
# MAE tests
# ---------------------------------------------------------------------------

class TestMAE:
    """Mean Absolute Error tests."""

    def test_perfect_predictions(self):
        """Zero error when estimated == reference."""
        est = [10.0, 20.0, 30.0]
        ref = [10.0, 20.0, 30.0]
        assert _mae(est, ref) == pytest.approx(0.0)

    def test_known_values(self):
        """MAE = (2 + 2 + 3) / 3 ≈ 2.333."""
        est = [10.0, 20.0, 30.0]
        ref = [12.0, 18.0, 33.0]
        expected = (2 + 2 + 3) / 3.0
        assert _mae(est, ref) == pytest.approx(expected, abs=0.001)

    def test_single_value(self):
        """Single data point."""
        assert _mae([5.0], [8.0]) == pytest.approx(3.0)

    def test_symmetry(self):
        """MAE(est, ref) == MAE(ref, est)."""
        est = [10.0, 20.0]
        ref = [12.0, 18.0]
        assert _mae(est, ref) == pytest.approx(_mae(ref, est))

    def test_empty_returns_nan(self):
        """Empty lists should return NaN."""
        assert np.isnan(_mae([], []))

    def test_negative_errors(self):
        """Overestimates and underestimates are treated the same."""
        est = [8.0, 12.0]  # under by 2, over by 2
        ref = [10.0, 10.0]
        assert _mae(est, ref) == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# RMSE tests
# ---------------------------------------------------------------------------

class TestRMSE:
    """Root Mean Square Error tests."""

    def test_perfect_predictions(self):
        """Zero error when estimated == reference."""
        est = [10.0, 20.0, 30.0]
        ref = [10.0, 20.0, 30.0]
        assert _rmse(est, ref) == pytest.approx(0.0)

    def test_known_values(self):
        """RMSE = sqrt((4 + 4 + 9) / 3) = sqrt(17/3) ≈ 2.380."""
        est = [10.0, 20.0, 30.0]
        ref = [12.0, 18.0, 33.0]
        expected = np.sqrt((4 + 4 + 9) / 3.0)
        assert _rmse(est, ref) == pytest.approx(expected, abs=0.001)

    def test_single_value(self):
        """Single data point: RMSE == absolute error."""
        assert _rmse([5.0], [8.0]) == pytest.approx(3.0)

    def test_rmse_ge_mae(self):
        """RMSE is always ≥ MAE for the same data."""
        est = [10.0, 20.0, 30.0]
        ref = [12.0, 18.0, 33.0]
        assert _rmse(est, ref) >= _mae(est, ref)

    def test_empty_returns_nan(self):
        """Empty lists should return NaN."""
        assert np.isnan(_rmse([], []))

    def test_large_outlier_dominates(self):
        """A single large error raises RMSE significantly."""
        est = [10.0, 10.0, 10.0, 10.0, 100.0]
        ref = [10.0, 10.0, 10.0, 10.0, 10.0]
        rmse = _rmse(est, ref)
        mae = _mae(est, ref)
        assert rmse > mae * 2  # RMSE is more sensitive to outliers


# ---------------------------------------------------------------------------
# Relative error tests
# ---------------------------------------------------------------------------

class TestRelativeError:
    """Relative error tests."""

    def test_known_value(self):
        """Relative error = |10-12|/12 ≈ 0.1667 (16.67%)."""
        re = _relative_error(10.0, 12.0)
        assert re == pytest.approx(2.0 / 12.0, abs=0.0001)

    def test_perfect(self):
        """Zero relative error for perfect estimate."""
        assert _relative_error(50.0, 50.0) == pytest.approx(0.0)

    def test_double_estimate(self):
        """Estimated 2x reference → 100% relative error."""
        assert _relative_error(20.0, 10.0) == pytest.approx(1.0)

    def test_zero_reference(self):
        """Zero reference distance → infinite relative error."""
        re = _relative_error(5.0, 0.0)
        assert re == float("inf")

    def test_overestimate_and_underestimate(self):
        """Relative error is unsigned (absolute)."""
        re_over = _relative_error(12.0, 10.0)   # over by 20%
        re_under = _relative_error(8.0, 10.0)    # under by 20%
        assert re_over == pytest.approx(re_under)

    def test_very_small_error(self):
        """Near-perfect estimate has small relative error."""
        re = _relative_error(10.001, 10.0)
        assert re < 0.001


# ---------------------------------------------------------------------------
# Tracking stability / jitter
# ---------------------------------------------------------------------------

class TestTrackingStability:
    """Test that tracking jitter can be measured correctly."""

    def test_stationary_low_jitter(self):
        """Stationary landmarks should have low positional jitter."""
        rng = np.random.default_rng(42)
        positions = [
            np.array([100.0 + rng.normal(0, 0.5),
                       200.0 + rng.normal(0, 0.5)])
            for _ in range(100)
        ]
        xs = np.array([p[0] for p in positions])
        ys = np.array([p[1] for p in positions])
        jitter = np.sqrt(np.std(xs) ** 2 + np.std(ys) ** 2)
        assert jitter < 2.0, f"Expected low jitter for stationary, got {jitter}"

    def test_moving_high_variation(self):
        """Linearly moving landmarks have high std (movement, not noise)."""
        positions = [np.array([100.0 + i, 200.0 + i]) for i in range(100)]
        xs = np.array([p[0] for p in positions])
        variation = np.std(xs)
        assert variation > 10.0, f"Expected high variation for movement, got {variation}"

    def test_jitter_after_detrending(self):
        """After removing the linear trend, jitter from noise is revealed."""
        rng = np.random.default_rng(42)
        # Linear movement + noise
        positions = [
            np.array([100.0 + i + rng.normal(0, 0.3),
                       200.0 + i + rng.normal(0, 0.3)])
            for i in range(100)
        ]
        xs = np.array([p[0] for p in positions])
        trend = np.polyval(np.polyfit(np.arange(len(xs)), xs, 1), np.arange(len(xs)))
        residual_std = np.std(xs - trend)
        assert residual_std < 1.0, f"Detrended jitter should be small, got {residual_std}"

    def test_zero_jitter(self):
        """Perfectly stationary point has zero jitter."""
        positions = [np.array([100.0, 200.0]) for _ in range(50)]
        xs = np.array([p[0] for p in positions])
        assert np.std(xs) == pytest.approx(0.0)

    def test_single_point_no_crash(self):
        """Single measurement should not crash jitter calculation."""
        positions = [np.array([100.0, 200.0])]
        xs = np.array([p[0] for p in positions])
        assert np.std(xs) == pytest.approx(0.0)

"""Tests for temporal smoothing filters.

Tests cover:
- Exponential Moving Average (EMA) filter
- One Euro Filter
- Kalman Filter
- Edge cases: alpha boundaries, step responses, speed adaptation
"""

import pytest
import numpy as np


# ---------------------------------------------------------------------------
# EMA reference implementation (for tests that don't need the real module)
# ---------------------------------------------------------------------------

def _ema(values: list[float], alpha: float) -> list[float]:
    """Apply Exponential Moving Average."""
    if not values:
        return []
    result = [values[0]]
    for v in values[1:]:
        result.append(alpha * v + (1 - alpha) * result[-1])
    return result


# ---------------------------------------------------------------------------
# EMA filter tests
# ---------------------------------------------------------------------------

class TestEMAFilter:
    """Tests for the Exponential Moving Average filter."""

    def test_basic_smoothing(self):
        """EMA output should be smoother than noisy input."""
        rng = np.random.default_rng(42)
        raw = [50.0 + rng.normal(0, 5) for _ in range(100)]
        smoothed = _ema(raw, alpha=0.3)

        raw_std = np.std(raw)
        smoothed_std = np.std(smoothed)
        assert smoothed_std < raw_std, \
            f"Smoothed std ({smoothed_std:.2f}) should be < raw std ({raw_std:.2f})"

    def test_alpha_zero_no_update(self):
        """Alpha=0 means the output never changes from the first value."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = _ema(values, alpha=0.0)
        assert all(v == pytest.approx(10.0) for v in result)

    def test_alpha_one_no_smoothing(self):
        """Alpha=1 means the output always equals the latest input."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = _ema(values, alpha=1.0)
        for original, filtered in zip(values, result):
            assert filtered == pytest.approx(original)

    def test_step_response_convergence(self):
        """After a step from 0 to 100, EMA should converge to 100."""
        values = [0.0] * 10 + [100.0] * 100
        result = _ema(values, alpha=0.3)
        # After many samples at 100, the output should be near 100
        assert result[-1] == pytest.approx(100.0, abs=0.01)

    def test_step_response_initial_lag(self):
        """EMA should lag behind a step input initially."""
        values = [0.0] * 10 + [100.0] * 5
        result = _ema(values, alpha=0.3)
        # Right after the step (index 10), output should still be below 100
        assert result[11] < 100.0

    def test_alpha_0_5_halving(self):
        """With alpha=0.5, each step halves the gap to the new value."""
        values = [0.0, 100.0, 100.0, 100.0]
        result = _ema(values, alpha=0.5)
        assert result[1] == pytest.approx(50.0)    # 0 + 0.5*(100-0)
        assert result[2] == pytest.approx(75.0)    # 50 + 0.5*(100-50)
        assert result[3] == pytest.approx(87.5)    # 75 + 0.5*(100-75)

    def test_empty_input(self):
        """Empty input should return empty output."""
        assert _ema([], 0.3) == []

    def test_single_value(self):
        """Single value should return that value."""
        assert _ema([42.0], 0.3) == [42.0]

    def test_constant_input(self):
        """Constant input should produce constant output."""
        values = [7.0] * 20
        result = _ema(values, alpha=0.3)
        for v in result:
            assert v == pytest.approx(7.0)


# ---------------------------------------------------------------------------
# One Euro Filter tests
# ---------------------------------------------------------------------------

class TestOneEuroFilter:
    """Tests for the One Euro Filter.

    These tests use the actual module when available, otherwise verify
    properties with a simplified implementation.
    """

    @pytest.fixture
    def filter_cls(self):
        """Try to import the real filter; skip if unavailable."""
        try:
            from backend.tracking.filters import OneEuroFilter
            return OneEuroFilter
        except ImportError:
            pytest.skip("OneEuroFilter module not yet available")

    def test_reduces_jitter(self, filter_cls):
        """Filter should reduce high-frequency noise on stationary signal."""
        rng = np.random.default_rng(42)
        flt = filter_cls(min_cutoff=1.0, beta=0.007, d_cutoff=1.0)

        raw_values = [50.0 + rng.normal(0, 3) for _ in range(200)]
        filtered = []
        for i, v in enumerate(raw_values):
            filtered.append(flt.filter(v, timestamp=i * 0.033))

        # Filtered output should have lower variance
        assert np.std(filtered[20:]) < np.std(raw_values), \
            "One Euro should reduce jitter"

    def test_preserves_slow_movement(self, filter_cls):
        """Filter should follow slow, steady movements."""
        flt = filter_cls(min_cutoff=1.0, beta=0.007, d_cutoff=1.0)

        # Slow linear ramp
        raw = [float(i) for i in range(100)]
        filtered = []
        for i, v in enumerate(raw):
            filtered.append(flt.filter(v, timestamp=i * 0.033))

        # After warm-up, filtered should closely track input
        final_error = abs(filtered[-1] - raw[-1])
        assert final_error < 5.0, \
            f"Should track slow movement, error = {final_error}"

    def test_handles_speed_change(self, filter_cls):
        """Filter should adapt when speed changes (stationary → fast)."""
        flt = filter_cls(min_cutoff=1.0, beta=0.5, d_cutoff=1.0)

        values = [50.0] * 50 + [50.0 + i * 2 for i in range(50)]
        filtered = []
        for i, v in enumerate(values):
            filtered.append(flt.filter(v, timestamp=i * 0.033))

        # During fast movement, filter should still follow
        assert filtered[-1] > 100.0, "Should follow fast movement"


# ---------------------------------------------------------------------------
# Kalman Filter tests
# ---------------------------------------------------------------------------

class TestKalmanFilter:
    """Tests for the Kalman Filter (1D tracking)."""

    @pytest.fixture
    def filter_cls(self):
        """Try to import the real filter; skip if unavailable."""
        try:
            from backend.tracking.filters import KalmanFilter1D
            return KalmanFilter1D
        except ImportError:
            pytest.skip("KalmanFilter1D module not yet available")

    def test_basic_tracking(self, filter_cls):
        """Should track a linearly moving target."""
        kf = filter_cls()
        positions = [float(i) * 2.0 for i in range(100)]
        filtered = []
        for p in positions:
            filtered.append(kf.update(p))

        # After warm-up, filtered should closely track
        assert abs(filtered[-1] - positions[-1]) < 5.0

    def test_noise_reduction(self, filter_cls):
        """Should reduce measurement noise."""
        rng = np.random.default_rng(42)
        kf = filter_cls()

        raw = [50.0 + rng.normal(0, 5) for _ in range(200)]
        filtered = [kf.update(v) for v in raw]

        assert np.std(filtered[50:]) < np.std(raw), \
            "Kalman filter should reduce noise variance"

    def test_single_update(self, filter_cls):
        """Single update should not crash."""
        kf = filter_cls()
        result = kf.update(42.0)
        assert isinstance(result, (int, float))

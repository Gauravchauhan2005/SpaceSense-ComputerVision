"""Tests for motion analysis (velocity, direction, acceleration).

Tests cover:
- Velocity calculation (pixels/s)
- Direction / heading calculation
- Acceleration
- Edge cases: zero movement, very fast movement
"""

import pytest
import math
import numpy as np


# ---------------------------------------------------------------------------
# Reference implementations for testing
# ---------------------------------------------------------------------------

def _velocity(p1: np.ndarray, p2: np.ndarray, dt: float) -> float:
    """Euclidean velocity in pixels/s."""
    if dt <= 0:
        return 0.0
    return float(np.linalg.norm(p2 - p1) / dt)


def _direction_deg(p1: np.ndarray, p2: np.ndarray) -> float:
    """Direction of movement in degrees (atan2 convention)."""
    diff = p2 - p1
    if np.linalg.norm(diff) == 0:
        return 0.0
    return float(math.degrees(math.atan2(diff[1], diff[0])))


def _acceleration(v1: float, v2: float, dt: float) -> float:
    """Acceleration = (v2 - v1) / dt."""
    if dt <= 0:
        return 0.0
    return (v2 - v1) / dt


# ---------------------------------------------------------------------------
# Velocity tests
# ---------------------------------------------------------------------------

class TestVelocityCalculation:
    """Test velocity = distance / dt."""

    def test_basic_velocity(self):
        """P1=(0,0), P2=(3,4) → dist=5. dt=0.5s → v=10 px/s."""
        p1 = np.array([0.0, 0.0])
        p2 = np.array([3.0, 4.0])
        v = _velocity(p1, p2, 0.5)
        assert v == pytest.approx(10.0)

    def test_horizontal_movement(self):
        """Horizontal movement: dist=10, dt=1 → v=10."""
        p1 = np.array([0.0, 0.0])
        p2 = np.array([10.0, 0.0])
        v = _velocity(p1, p2, 1.0)
        assert v == pytest.approx(10.0)

    def test_vertical_movement(self):
        """Vertical movement: dist=20, dt=2 → v=10."""
        p1 = np.array([0.0, 0.0])
        p2 = np.array([0.0, 20.0])
        v = _velocity(p1, p2, 2.0)
        assert v == pytest.approx(10.0)

    def test_no_movement(self):
        """Zero displacement → zero velocity."""
        p = np.array([50.0, 50.0])
        v = _velocity(p, p.copy(), 1.0)
        assert v == pytest.approx(0.0)

    def test_zero_dt(self):
        """Zero dt should return 0 (or be handled gracefully)."""
        p1 = np.array([0.0, 0.0])
        p2 = np.array([10.0, 0.0])
        v = _velocity(p1, p2, 0.0)
        assert v == 0.0

    def test_negative_dt(self):
        """Negative dt should return 0."""
        p1 = np.array([0.0, 0.0])
        p2 = np.array([10.0, 0.0])
        v = _velocity(p1, p2, -1.0)
        assert v == 0.0

    def test_very_small_dt(self):
        """Very small dt produces very large velocity (not infinite)."""
        p1 = np.array([0.0, 0.0])
        p2 = np.array([1.0, 0.0])
        v = _velocity(p1, p2, 0.001)
        assert v == pytest.approx(1000.0)

    def test_velocity_is_positive(self):
        """Velocity (speed) is always non-negative."""
        p1 = np.array([10.0, 10.0])
        p2 = np.array([5.0, 5.0])  # moving backward
        v = _velocity(p1, p2, 1.0)
        assert v >= 0.0

    def test_3d_velocity(self):
        """Velocity with 3D points."""
        p1 = np.array([0.0, 0.0, 0.0])
        p2 = np.array([1.0, 2.0, 2.0])
        v = _velocity(p1, p2, 1.0)
        assert v == pytest.approx(3.0)  # sqrt(1+4+4) = 3


# ---------------------------------------------------------------------------
# Direction tests
# ---------------------------------------------------------------------------

class TestDirectionCalculation:
    """Test direction / heading angle."""

    def test_right(self):
        """Moving right → 0°."""
        d = _direction_deg(np.array([0.0, 0.0]), np.array([1.0, 0.0]))
        assert abs(d) < 0.01

    def test_down(self):
        """Moving down (positive y in image) → 90°."""
        d = _direction_deg(np.array([0.0, 0.0]), np.array([0.0, 1.0]))
        assert abs(d - 90.0) < 0.01

    def test_left(self):
        """Moving left → ±180°."""
        d = _direction_deg(np.array([0.0, 0.0]), np.array([-1.0, 0.0]))
        assert abs(abs(d) - 180.0) < 0.01

    def test_up(self):
        """Moving up (negative y in image) → -90°."""
        d = _direction_deg(np.array([0.0, 0.0]), np.array([0.0, -1.0]))
        assert abs(d - (-90.0)) < 0.01

    def test_diagonal_45(self):
        """Moving right+down → 45°."""
        d = _direction_deg(np.array([0.0, 0.0]), np.array([1.0, 1.0]))
        assert abs(d - 45.0) < 0.01

    def test_no_movement(self):
        """Zero displacement → 0°."""
        d = _direction_deg(np.array([5.0, 5.0]), np.array([5.0, 5.0]))
        assert d == 0.0

    def test_direction_range(self):
        """Direction should be in [-180, 180]."""
        for angle_rad in np.linspace(0, 2 * np.pi, 36):
            p2 = np.array([np.cos(angle_rad), np.sin(angle_rad)])
            d = _direction_deg(np.array([0.0, 0.0]), p2)
            assert -180.0 <= d <= 180.0


# ---------------------------------------------------------------------------
# Acceleration tests
# ---------------------------------------------------------------------------

class TestAcceleration:
    """Test acceleration = (v2 - v1) / dt."""

    def test_basic_acceleration(self):
        """v1=10, v2=20, dt=2 → a=5 px/s²."""
        a = _acceleration(10.0, 20.0, 2.0)
        assert a == pytest.approx(5.0)

    def test_deceleration(self):
        """v1=20, v2=10, dt=2 → a=-5 px/s²."""
        a = _acceleration(20.0, 10.0, 2.0)
        assert a == pytest.approx(-5.0)

    def test_constant_velocity(self):
        """v1 == v2 → a=0."""
        a = _acceleration(15.0, 15.0, 1.0)
        assert a == pytest.approx(0.0)

    def test_zero_dt(self):
        """Zero dt should return 0."""
        a = _acceleration(10.0, 20.0, 0.0)
        assert a == 0.0

    def test_from_rest(self):
        """Starting from rest: v1=0, v2=30, dt=3 → a=10."""
        a = _acceleration(0.0, 30.0, 3.0)
        assert a == pytest.approx(10.0)

    def test_to_rest(self):
        """Coming to rest: v1=30, v2=0, dt=3 → a=-10."""
        a = _acceleration(30.0, 0.0, 3.0)
        assert a == pytest.approx(-10.0)

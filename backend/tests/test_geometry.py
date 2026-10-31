"""Tests for the AngleCalculator geometry module.

Tests cover:
- 3-point angle calculation (2D and 3D)
- Movement angle calculation
- Hand orientation analysis
- Edge cases: zero vectors, None inputs, degenerate geometries
"""

import pytest
import numpy as np

# Import will succeed once the backend module is built by the other subagent
from backend.geometry.angle_calculator import AngleCalculator


# ---------------------------------------------------------------------------
# calculate_angle_3points
# ---------------------------------------------------------------------------

class TestCalculateAngle3Points:
    """Tests for AngleCalculator.calculate_angle_3points(a, b, c).

    The method computes the angle ∠ABC formed at vertex B by rays BA and BC.
    """

    def test_right_angle(self):
        """90-degree angle at the origin."""
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 0.0])
        c = np.array([0.0, 1.0])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert abs(angle - 90.0) < 0.01, f"Expected ~90°, got {angle}"

    def test_straight_line(self):
        """180-degree angle (collinear points)."""
        a = np.array([-1.0, 0.0])
        b = np.array([0.0, 0.0])
        c = np.array([1.0, 0.0])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert abs(angle - 180.0) < 0.01, f"Expected ~180°, got {angle}"

    def test_acute_angle_45(self):
        """45-degree angle."""
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 0.0])
        c = np.array([1.0, 1.0])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert abs(angle - 45.0) < 0.01, f"Expected ~45°, got {angle}"

    def test_obtuse_angle_135(self):
        """135-degree angle."""
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 0.0])
        c = np.array([-1.0, 1.0])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert abs(angle - 135.0) < 0.01, f"Expected ~135°, got {angle}"

    def test_60_degree_angle(self):
        """60-degree angle (equilateral triangle vertex)."""
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 0.0])
        c = np.array([0.5, np.sqrt(3) / 2])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert abs(angle - 60.0) < 0.01, f"Expected ~60°, got {angle}"

    def test_zero_length_vector_a_equals_b(self):
        """When A == B the ray BA has zero length; should return 0."""
        a = np.array([1.0, 1.0])
        b = np.array([1.0, 1.0])
        c = np.array([2.0, 2.0])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert angle == 0.0, f"Expected 0° for degenerate input, got {angle}"

    def test_zero_length_vector_b_equals_c(self):
        """When B == C the ray BC has zero length; should return 0."""
        a = np.array([2.0, 2.0])
        b = np.array([1.0, 1.0])
        c = np.array([1.0, 1.0])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert angle == 0.0, f"Expected 0° for degenerate input, got {angle}"

    def test_all_same_point(self):
        """All three points identical — fully degenerate case."""
        p = np.array([5.0, 5.0])
        angle = AngleCalculator.calculate_angle_3points(p, p.copy(), p.copy())
        assert angle == 0.0

    def test_3d_right_angle(self):
        """90-degree angle with 3-D coordinates."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([0.0, 0.0, 0.0])
        c = np.array([0.0, 1.0, 0.0])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert abs(angle - 90.0) < 0.01

    def test_3d_diagonal(self):
        """Angle between two 3-D rays."""
        a = np.array([1.0, 1.0, 0.0])
        b = np.array([0.0, 0.0, 0.0])
        c = np.array([0.0, 1.0, 1.0])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert 0.0 < angle < 180.0  # sanity: non-degenerate

    def test_very_small_angle(self):
        """Nearly parallel vectors → angle close to 0°."""
        a = np.array([1.0, 0.001])
        b = np.array([0.0, 0.0])
        c = np.array([1.0, 0.0])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert angle < 1.0, f"Expected < 1°, got {angle}"

    def test_nearly_straight_line(self):
        """Nearly 180° — vectors almost anti-parallel."""
        a = np.array([-1.0, 0.001])
        b = np.array([0.0, 0.0])
        c = np.array([1.0, 0.0])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert angle > 179.0, f"Expected > 179°, got {angle}"

    def test_none_input_a(self):
        """None for first point should return 0."""
        angle = AngleCalculator.calculate_angle_3points(
            None, np.array([0, 0]), np.array([1, 1])
        )
        assert angle == 0.0

    def test_none_input_b(self):
        """None for vertex should return 0."""
        angle = AngleCalculator.calculate_angle_3points(
            np.array([1, 0]), None, np.array([0, 1])
        )
        assert angle == 0.0

    def test_none_input_c(self):
        """None for third point should return 0."""
        angle = AngleCalculator.calculate_angle_3points(
            np.array([1, 0]), np.array([0, 0]), None
        )
        assert angle == 0.0

    def test_all_none(self):
        """All inputs None should return 0."""
        angle = AngleCalculator.calculate_angle_3points(None, None, None)
        assert angle == 0.0

    def test_symmetry(self):
        """Angle should be the same if A and C are swapped."""
        a = np.array([3.0, 1.0])
        b = np.array([0.0, 0.0])
        c = np.array([1.0, 3.0])
        angle_abc = AngleCalculator.calculate_angle_3points(a, b, c)
        angle_cba = AngleCalculator.calculate_angle_3points(c, b, a)
        assert abs(angle_abc - angle_cba) < 0.01

    def test_large_coordinates(self):
        """Angles should be independent of scale."""
        scale = 1e6
        a = np.array([scale, 0.0])
        b = np.array([0.0, 0.0])
        c = np.array([0.0, scale])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert abs(angle - 90.0) < 0.01

    def test_tiny_coordinates(self):
        """Very small coordinates should still compute correctly."""
        scale = 1e-8
        a = np.array([scale, 0.0])
        b = np.array([0.0, 0.0])
        c = np.array([0.0, scale])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert abs(angle - 90.0) < 0.5  # allow slight numerical imprecision

    def test_negative_coordinates(self):
        """Negative coordinates should work the same as positive."""
        a = np.array([-1.0, 0.0])
        b = np.array([0.0, 0.0])
        c = np.array([0.0, -1.0])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert abs(angle - 90.0) < 0.01

    def test_integer_array_input(self):
        """Integer numpy arrays should work (auto-cast)."""
        a = np.array([1, 0])
        b = np.array([0, 0])
        c = np.array([0, 1])
        angle = AngleCalculator.calculate_angle_3points(a, b, c)
        assert abs(angle - 90.0) < 0.01


# ---------------------------------------------------------------------------
# calculate_movement_angle
# ---------------------------------------------------------------------------

class TestMovementAngle:
    """Tests for AngleCalculator.calculate_movement_angle(prev, curr).

    Returns the heading in degrees of the movement vector (curr - prev).
    """

    def test_right(self):
        """Moving right → 0° (or near 0°)."""
        angle = AngleCalculator.calculate_movement_angle(
            np.array([0.0, 0.0]), np.array([1.0, 0.0])
        )
        assert abs(angle - 0.0) < 0.01 or abs(angle - 360.0) < 0.01

    def test_left(self):
        """Moving left → ±180°."""
        angle = AngleCalculator.calculate_movement_angle(
            np.array([0.0, 0.0]), np.array([-1.0, 0.0])
        )
        assert abs(abs(angle) - 180.0) < 0.01

    def test_down(self):
        """Moving down in image coords (positive y) → 90° or equivalent."""
        angle = AngleCalculator.calculate_movement_angle(
            np.array([0.0, 0.0]), np.array([0.0, 1.0])
        )
        assert abs(angle - 90.0) < 0.01 or abs(angle - (-270.0)) < 0.01

    def test_up(self):
        """Moving up in image coordinates (negative y direction)."""
        angle = AngleCalculator.calculate_movement_angle(
            np.array([0.0, 0.0]), np.array([0.0, -1.0])
        )
        # Depending on convention this could be -90 or 270
        assert abs(angle - (-90.0)) < 0.01 or abs(angle - 270.0) < 0.01

    def test_diagonal_down_right(self):
        """45° diagonal movement (right and down)."""
        angle = AngleCalculator.calculate_movement_angle(
            np.array([0.0, 0.0]), np.array([1.0, 1.0])
        )
        assert abs(angle - 45.0) < 0.01

    def test_diagonal_up_left(self):
        """Diagonal movement up-left."""
        angle = AngleCalculator.calculate_movement_angle(
            np.array([0.0, 0.0]), np.array([-1.0, -1.0])
        )
        # Should be -135 or 225
        assert abs(angle - (-135.0)) < 0.01 or abs(angle - 225.0) < 0.01

    def test_no_movement(self):
        """Zero displacement should return 0."""
        angle = AngleCalculator.calculate_movement_angle(
            np.array([5.0, 5.0]), np.array([5.0, 5.0])
        )
        assert angle == 0.0

    def test_none_input_prev(self):
        """None for previous position should return 0."""
        angle = AngleCalculator.calculate_movement_angle(
            None, np.array([1, 1])
        )
        assert angle == 0.0

    def test_none_input_curr(self):
        """None for current position should return 0."""
        angle = AngleCalculator.calculate_movement_angle(
            np.array([1, 1]), None
        )
        assert angle == 0.0

    def test_both_none(self):
        """Both inputs None should return 0."""
        angle = AngleCalculator.calculate_movement_angle(None, None)
        assert angle == 0.0

    def test_very_small_displacement(self):
        """Sub-pixel movement should still return a valid angle."""
        angle = AngleCalculator.calculate_movement_angle(
            np.array([100.0, 100.0]), np.array([100.0001, 100.0])
        )
        # Should be approximately 0° (rightward)
        assert abs(angle) < 1.0 or abs(angle - 360.0) < 1.0


# ---------------------------------------------------------------------------
# calculate_hand_orientation
# ---------------------------------------------------------------------------

class TestHandOrientation:
    """Tests for AngleCalculator.calculate_hand_orientation(landmarks).

    Expects a dict mapping landmark index → np.array of (x, y) coordinates.
    Returns a dict with orientation info including 'rotation_deg'.
    """

    def test_vertical_hand(self):
        """Hand pointing straight up — wrist below, middle MCP above."""
        landmarks = {
            0: np.array([0.5, 0.8]),    # wrist
            9: np.array([0.5, 0.4]),    # middle finger MCP
            5: np.array([0.4, 0.5]),    # index MCP
            17: np.array([0.6, 0.5]),   # pinky MCP
        }
        result = AngleCalculator.calculate_hand_orientation(landmarks)
        assert result is not None
        assert "rotation_deg" in result

    def test_horizontal_hand(self):
        """Hand rotated 90° — wrist at left, fingers pointing right."""
        landmarks = {
            0: np.array([0.2, 0.5]),    # wrist
            9: np.array([0.6, 0.5]),    # middle finger MCP
            5: np.array([0.4, 0.4]),    # index MCP
            17: np.array([0.4, 0.6]),   # pinky MCP
        }
        result = AngleCalculator.calculate_hand_orientation(landmarks)
        assert result is not None
        assert "rotation_deg" in result

    def test_empty_landmarks(self):
        """Empty landmark dict should return None or empty result."""
        result = AngleCalculator.calculate_hand_orientation({})
        # Implementation may return None when required landmarks are missing
        assert result is None or result == {}

    def test_none_landmarks(self):
        """None input should not crash."""
        result = AngleCalculator.calculate_hand_orientation(None)
        assert result is None or result == {}

    def test_missing_required_landmark(self):
        """Missing wrist (index 0) should handle gracefully."""
        landmarks = {
            9: np.array([0.5, 0.4]),
            5: np.array([0.4, 0.5]),
            17: np.array([0.6, 0.5]),
        }
        result = AngleCalculator.calculate_hand_orientation(landmarks)
        # Should return None or handle gracefully
        assert result is None or isinstance(result, dict)

    def test_rotation_returns_numeric(self):
        """rotation_deg should be a finite number."""
        landmarks = {
            0: np.array([0.5, 0.8]),
            9: np.array([0.5, 0.4]),
            5: np.array([0.4, 0.5]),
            17: np.array([0.6, 0.5]),
        }
        result = AngleCalculator.calculate_hand_orientation(landmarks)
        assert result is not None
        assert np.isfinite(result["rotation_deg"])

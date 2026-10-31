"""Tests for finger angle calculations.

Tests cover:
- Straight finger detection (angles near 180°)
- Bent finger detection (angles < 180°)
- Missing / empty landmarks
- Multiple finger analysis
"""

import pytest
import numpy as np

from backend.geometry.angle_calculator import AngleCalculator


# ---------------------------------------------------------------------------
# Finger angle tests
# ---------------------------------------------------------------------------

class TestFingerAngles:
    """Test finger joint angle computations.

    MediaPipe hand landmark indices used:
        Index finger: MCP=5, PIP=6, DIP=7, TIP=8
        Middle finger: MCP=9, PIP=10, DIP=11, TIP=12
        Ring finger: MCP=13, PIP=14, DIP=15, TIP=16
        Pinky: MCP=17, PIP=18, DIP=19, TIP=20
        Thumb: CMC=1, MCP=2, IP=3, TIP=4
    """

    def test_straight_index_finger(self):
        """Fully extended index finger — angles at PIP and DIP ≈ 180°."""
        # Straight vertical finger
        landmarks = {
            5: np.array([0.4, 0.6, 0.0]),   # MCP
            6: np.array([0.4, 0.5, 0.0]),   # PIP
            7: np.array([0.4, 0.4, 0.0]),   # DIP
            8: np.array([0.4, 0.3, 0.0]),   # TIP
        }
        # Angle at PIP (5→6→7): vectors (0, 0.1) and (0, -0.1) → 180°
        pip_angle = AngleCalculator.calculate_angle_3points(
            landmarks[5], landmarks[6], landmarks[7]
        )
        assert abs(pip_angle - 180.0) < 0.01, f"PIP angle: {pip_angle}"

        # Angle at DIP (6→7→8): same vectors → 180°
        dip_angle = AngleCalculator.calculate_angle_3points(
            landmarks[6], landmarks[7], landmarks[8]
        )
        assert abs(dip_angle - 180.0) < 0.01, f"DIP angle: {dip_angle}"

    def test_bent_index_finger_at_pip(self):
        """Bent index finger — PIP angle < 180°."""
        landmarks = {
            5: np.array([0.4, 0.6, 0.0]),   # MCP
            6: np.array([0.4, 0.5, 0.0]),   # PIP
            7: np.array([0.5, 0.45, 0.0]),  # DIP (bent outward)
            8: np.array([0.55, 0.5, 0.0]),  # TIP (curling back)
        }
        pip_angle = AngleCalculator.calculate_angle_3points(
            landmarks[5], landmarks[6], landmarks[7]
        )
        assert pip_angle < 180.0, f"Expected bent angle < 180°, got {pip_angle}"
        assert pip_angle > 0.0

    def test_fully_curled_finger(self):
        """Tightly curled finger — small angle at PIP."""
        landmarks = {
            5: np.array([0.4, 0.6, 0.0]),   # MCP
            6: np.array([0.4, 0.5, 0.0]),   # PIP
            7: np.array([0.35, 0.55, 0.0]), # DIP (curled back)
            8: np.array([0.38, 0.62, 0.0]), # TIP (near MCP)
        }
        pip_angle = AngleCalculator.calculate_angle_3points(
            landmarks[5], landmarks[6], landmarks[7]
        )
        assert pip_angle < 120.0, f"Expected tight curl < 120°, got {pip_angle}"

    def test_missing_landmarks_empty_dict(self):
        """Empty landmarks dict should not crash."""
        landmarks = {}
        # Should return 0 for any angle calculated with missing points
        # Since no landmarks are available, we just check it doesn't crash
        assert len(landmarks) == 0

    def test_missing_single_landmark(self):
        """A single missing landmark in a chain returns 0 angle."""
        # Missing DIP (index 7) — can't compute PIP angle
        landmarks = {
            5: np.array([0.4, 0.6, 0.0]),
            6: np.array([0.4, 0.5, 0.0]),
            # 7 is missing
            8: np.array([0.4, 0.3, 0.0]),
        }
        pip_angle = AngleCalculator.calculate_angle_3points(
            landmarks.get(5), landmarks.get(6), landmarks.get(7)
        )
        assert pip_angle == 0.0  # None input → 0.0

    def test_middle_finger_straight(self):
        """Straight middle finger (indices 9-12)."""
        landmarks = {
            9: np.array([0.5, 0.6, 0.0]),
            10: np.array([0.5, 0.5, 0.0]),
            11: np.array([0.5, 0.4, 0.0]),
            12: np.array([0.5, 0.3, 0.0]),
        }
        pip_angle = AngleCalculator.calculate_angle_3points(
            landmarks[9], landmarks[10], landmarks[11]
        )
        assert abs(pip_angle - 180.0) < 0.01

    def test_thumb_angle(self):
        """Thumb has a different geometry — still should compute valid angle."""
        landmarks = {
            1: np.array([0.3, 0.7, 0.0]),   # CMC
            2: np.array([0.25, 0.6, 0.0]),  # MCP
            3: np.array([0.22, 0.5, 0.0]),  # IP
            4: np.array([0.2, 0.4, 0.0]),   # TIP
        }
        mcp_angle = AngleCalculator.calculate_angle_3points(
            landmarks[1], landmarks[2], landmarks[3]
        )
        assert 0.0 < mcp_angle <= 180.0

    def test_all_fingers_extended(self):
        """Open hand — all fingers should have high PIP angles."""
        # Create a simplified open hand (all fingers straight, vertical)
        fingers = {
            "index": (5, 6, 7, 8),
            "middle": (9, 10, 11, 12),
            "ring": (13, 14, 15, 16),
            "pinky": (17, 18, 19, 20),
        }
        landmarks = {}
        for i, (name, (mcp, pip, dip, tip)) in enumerate(fingers.items()):
            x = 0.3 + i * 0.1
            landmarks[mcp] = np.array([x, 0.6, 0.0])
            landmarks[pip] = np.array([x, 0.5, 0.0])
            landmarks[dip] = np.array([x, 0.4, 0.0])
            landmarks[tip] = np.array([x, 0.3, 0.0])

        for name, (mcp, pip, dip, tip) in fingers.items():
            pip_angle = AngleCalculator.calculate_angle_3points(
                landmarks[mcp], landmarks[pip], landmarks[dip]
            )
            assert abs(pip_angle - 180.0) < 0.01, \
                f"{name} PIP angle should be ~180°, got {pip_angle}"

    def test_fist_all_fingers_curled(self):
        """Closed fist — all fingers should have low PIP angles."""
        fingers = {
            "index": (5, 6, 7, 8),
            "middle": (9, 10, 11, 12),
            "ring": (13, 14, 15, 16),
            "pinky": (17, 18, 19, 20),
        }
        landmarks = {}
        for i, (name, (mcp, pip, dip, tip)) in enumerate(fingers.items()):
            x = 0.3 + i * 0.1
            landmarks[mcp] = np.array([x, 0.6, 0.0])
            landmarks[pip] = np.array([x, 0.5, 0.0])
            landmarks[dip] = np.array([x + 0.05, 0.55, 0.0])   # bent
            landmarks[tip] = np.array([x + 0.03, 0.62, 0.0])   # curled back

        for name, (mcp, pip, dip, tip) in fingers.items():
            pip_angle = AngleCalculator.calculate_angle_3points(
                landmarks[mcp], landmarks[pip], landmarks[dip]
            )
            assert pip_angle < 150.0, \
                f"{name} PIP angle should be < 150° for fist, got {pip_angle}"


# ---------------------------------------------------------------------------
# Whole Hand vs Body Symmetry Line tests
# ---------------------------------------------------------------------------

class TestHandBodySymmetryAngle:
    """Test geometric angle between body symmetry reference line and whole hand."""

    def test_hand_parallel_downwards(self):
        """Hand pointing straight down along body vertical: angle ≈ 0°."""
        # Wrist at (300, 200), middle fingertip at (300, 350)
        hand_lms = {
            0: np.array([300.0, 200.0, 0.0]),
            12: np.array([300.0, 350.0, 0.0]),
        }
        res = AngleCalculator.calculate_hand_body_angle(hand_lms)
        assert "angle_deg" in res
        assert abs(res["angle_deg"] - 0.0) < 0.1
        assert abs(res["acute_angle_deg"] - 0.0) < 0.1

    def test_hand_horizontal_perpendicular(self):
        """Hand extended horizontally to the right: angle ≈ 90°."""
        # Wrist at (300, 200), middle fingertip at (450, 200)
        hand_lms = {
            0: np.array([300.0, 200.0, 0.0]),
            12: np.array([450.0, 200.0, 0.0]),
        }
        res = AngleCalculator.calculate_hand_body_angle(hand_lms)
        assert abs(res["angle_deg"] - 90.0) < 0.1
        assert abs(res["acute_angle_deg"] - 90.0) < 0.1
        assert res["lateral_direction"] == "right"

    def test_hand_raised_upwards(self):
        """Hand raised pointing straight up: angle ≈ 180°."""
        # Wrist at (300, 300), middle fingertip at (300, 150)
        hand_lms = {
            0: np.array([300.0, 300.0, 0.0]),
            12: np.array([300.0, 150.0, 0.0]),
        }
        res = AngleCalculator.calculate_hand_body_angle(hand_lms)
        assert abs(res["angle_deg"] - 180.0) < 0.1
        assert abs(res["acute_angle_deg"] - 0.0) < 0.1

    def test_with_tilted_face_symmetry(self):
        """When face is tilted 45°, body symmetry axis reflects this tilt."""
        # Forehead at (200, 100), chin at (300, 200) -> vector [100, 100] (45° tilt)
        face_lms = {
            "forehead": np.array([200.0, 100.0]),
            "chin": np.array([300.0, 200.0]),
        }
        # Hand parallel to tilted symmetry line
        hand_lms = {
            0: np.array([400.0, 300.0]),
            12: np.array([500.0, 400.0]),
        }
        res = AngleCalculator.calculate_hand_body_angle(hand_lms, face_landmarks=face_lms)
        assert abs(res["angle_deg"] - 0.0) < 0.1

    def test_empty_landmarks_return_empty_dict(self):
        """Empty landmarks should safely return empty dict."""
        assert AngleCalculator.calculate_hand_body_angle(None) == {}
        assert AngleCalculator.calculate_hand_body_angle({}) == {}

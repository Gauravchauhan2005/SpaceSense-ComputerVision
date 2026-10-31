"""Unit tests for HandTracker and FrameProcessor handedness logic.

Verifies:
- Handedness inversion when flip_handedness is True (selfie/mirror mode)
- Preserving MediaPipe raw handedness when flip_handedness is False
- FrameProcessor propagating mirror flag to HandTracker
"""

from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from backend.models import Handedness
from backend.vision.hand_tracker import HandTracker
from backend.vision.frame_processor import FrameProcessor


class TestHandednessLogic:
    """Test handedness mapping under normal and mirrored camera setups."""

    def test_flip_handedness_properties(self):
        """Verify flip_handedness property getter and setter."""
        with patch("backend.vision.hand_tracker.vision.HandLandmarker.create_from_options"):
            tracker = HandTracker(flip_handedness=True)
            assert tracker.flip_handedness is True

            tracker.flip_handedness = False
            assert tracker.flip_handedness is False

    def test_frame_processor_mirror_sync(self):
        """FrameProcessor with mirror=True should set HandTracker.flip_handedness=True."""
        with patch("backend.vision.hand_tracker.vision.HandLandmarker.create_from_options"):
            with patch("backend.vision.face_tracker.vision.FaceLandmarker.create_from_options"):
                proc = FrameProcessor(mirror=True)
                assert proc._hand_tracker.flip_handedness is True

                proc.mirror = False
                assert proc._hand_tracker.flip_handedness is False

                proc.mirror = True
                assert proc._hand_tracker.flip_handedness is True

    def test_handedness_inversion_in_process(self):
        """When flip_handedness=True, MediaPipe 'Left' becomes Handedness.RIGHT, 'Right' becomes Handedness.LEFT."""
        with patch("backend.vision.hand_tracker.vision.HandLandmarker.create_from_options") as mock_create:
            mock_landmarker = MagicMock()
            mock_create.return_value = mock_landmarker

            # Mock landmark coordinates (21 points)
            mock_pt = MagicMock(x=0.5, y=0.5, z=0.0)
            mock_landmarks = [[mock_pt] * 21]

            # Case 1: MediaPipe reports 'Left' under flip_handedness=True
            category_mock = MagicMock(category_name="Left", score=0.95)
            mock_landmarker.detect.return_value = MagicMock(
                hand_landmarks=mock_landmarks,
                handedness=[[category_mock]],
            )

            tracker_flipped = HandTracker(flip_handedness=True)
            dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            result = tracker_flipped.process(dummy_frame)

            assert result.detected is True
            assert result.hand_count == 1
            assert result.hands[0].handedness == Handedness.RIGHT
            assert result.right_hand is not None
            assert result.left_hand is None

            # Case 2: MediaPipe reports 'Right' under flip_handedness=True
            category_mock.category_name = "Right"
            result2 = tracker_flipped.process(dummy_frame)
            assert result2.hands[0].handedness == Handedness.LEFT
            assert result2.left_hand is not None
            assert result2.right_hand is None

            # Case 3: flip_handedness=False preserves MediaPipe label
            tracker_raw = HandTracker(flip_handedness=False)
            category_mock.category_name = "Left"
            result3 = tracker_raw.process(dummy_frame)
            assert result3.hands[0].handedness == Handedness.LEFT

            category_mock.category_name = "Right"
            result4 = tracker_raw.process(dummy_frame)
            assert result4.hands[0].handedness == Handedness.RIGHT

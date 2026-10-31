"""Integration tests for calibration workflows and endpoints."""

import pytest
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from backend.geometry.distance_estimator import DistanceEstimator
from backend.geometry.camera_calibration import CameraCalibration
from backend.models import (
    FaceTrackingResult,
    SingleFaceResult,
    FaceLandmarks,
    Point2D,
    BoundingBox,
    ScreenGeometry,
)


@pytest.fixture
def temp_calib_dir():
    temp_dir = Path("data") / "test_calib_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    yield temp_dir
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)


class TestCalibrationWorkflows:
    """Test reference distance and camera calibration logic."""

    def test_reference_calibration_calculation(self, temp_calib_dir):
        """Test calibrate_reference calculates and stores scale factor."""
        estimator = DistanceEstimator(focal_length_px=600.0, calibration_dir=temp_calib_dir)
        assert estimator.is_calibrated is False

        # Mock a face with inter-pupillary distance of 65px
        mock_face = SingleFaceResult(
            landmarks=FaceLandmarks(),
            confidence=0.95,
            inter_eye_distance_px=65.0,
            face_width_px=140.0,
        )
        face_result = FaceTrackingResult(
            detected=True,
            face_count=1,
            faces=[mock_face],
            primary_face=mock_face,
        )

        # Calibrate at 60cm
        cal = estimator.calibrate_reference(
            reference_distance_cm=60.0,
            face_result=face_result,
        )

        assert cal is not None
        assert estimator.is_calibrated is True
        assert cal.scale_factor is not None
        assert cal.scale_factor > 0

        # Reset calibration
        estimator.reset_calibration()
        assert estimator.is_calibrated is False
        assert estimator.ref_calibration is None

    def test_screen_geometry_persistence(self, temp_calib_dir):
        """Test setting and getting screen geometry."""
        estimator = DistanceEstimator(focal_length_px=600.0, calibration_dir=temp_calib_dir)
        geom = ScreenGeometry(
            screen_width_cm=35.0,
            screen_height_cm=20.0,
            camera_offset_x_cm=0.0,
            camera_offset_y_cm=1.0,
        )
        estimator.set_screen_geometry(geom)

        saved = estimator.get_screen_geometry()
        assert saved is not None
        assert saved.screen_width_cm == 35.0
        assert saved.screen_height_cm == 20.0
        assert saved.camera_offset_x_cm == 0.0
        assert saved.camera_offset_y_cm == 1.0

    def test_camera_calibration_reset(self, temp_calib_dir):
        """Test camera calibration state and reset."""
        calib = CameraCalibration(calibration_dir=temp_calib_dir)
        assert calib.collected_frames == 0

        calib.reset()
        assert calib.collected_frames == 0
        assert calib.intrinsic is None

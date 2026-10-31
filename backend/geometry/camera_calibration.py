"""
SpaceSense AI — Camera Calibration

Provides intrinsic camera calibration via OpenCV's checkerboard workflow,
plus reference-distance and screen-geometry calibration helpers.
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from backend.models import CalibrationStatus, IntrinsicCalibration, ScreenGeometry

logger = logging.getLogger(__name__)

_DEFAULT_CALIBRATION_DIR = Path("calibration")
_INTRINSIC_FILE = "intrinsic_calibration.json"


class CameraCalibration:
    """OpenCV checkerboard-based intrinsic camera calibration.

    Parameters
    ----------
    board_size : tuple[int, int]
        Number of *inner corners* on the checkerboard (cols, rows).
        Default ``(9, 6)``.
    square_size_mm : float
        Side length of a single square in millimetres.  Default ``25.0``.
    calibration_dir : str or Path
        Directory for storing calibration artefacts.
    """

    def __init__(
        self,
        board_size: tuple[int, int] = (9, 6),
        square_size_mm: float = 25.0,
        calibration_dir: str | Path = _DEFAULT_CALIBRATION_DIR,
    ) -> None:
        self._board_size = board_size
        self._square_size_mm = square_size_mm
        self._calibration_dir = Path(calibration_dir)

        # Calibration state
        self._status: CalibrationStatus = CalibrationStatus.UNCALIBRATED
        self._intrinsic: Optional[IntrinsicCalibration] = None

        # Collected calibration frames (object points + image points)
        self._obj_points: list[np.ndarray] = []
        self._img_points: list[np.ndarray] = []
        self._image_size: Optional[tuple[int, int]] = None  # (w, h)

        # Prepare the ideal 3-D object points for one board view
        # (z = 0 for all points on the flat board)
        cols, rows = board_size
        self._board_obj_pts = np.zeros((cols * rows, 3), np.float32)
        self._board_obj_pts[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
        self._board_obj_pts *= square_size_mm

        # Attempt to load a previously saved calibration
        self._load_calibration()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def status(self) -> CalibrationStatus:
        return self._status

    @property
    def intrinsic(self) -> Optional[IntrinsicCalibration]:
        return self._intrinsic

    @property
    def collected_frames(self) -> int:
        """Number of valid calibration frames collected so far."""
        return len(self._img_points)

    # ------------------------------------------------------------------
    # Checkerboard detection
    # ------------------------------------------------------------------

    def add_calibration_frame(self, frame: np.ndarray) -> bool:
        """Detect checkerboard corners in *frame* and store them.

        Returns *True* if corners were found (frame was useful).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        self._image_size = (w, h)

        found, corners = cv2.findChessboardCorners(
            gray, self._board_size,
            cv2.CALIB_CB_ADAPTIVE_THRESH
            | cv2.CALIB_CB_FAST_CHECK
            | cv2.CALIB_CB_NORMALIZE_IMAGE,
        )

        if not found or corners is None:
            return False

        # Subpixel refinement
        criteria = (
            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001
        )
        corners_refined = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

        self._obj_points.append(self._board_obj_pts.copy())
        self._img_points.append(corners_refined)
        self._status = CalibrationStatus.IN_PROGRESS

        logger.info(
            "Calibration frame %d accepted (%dx%d).",
            len(self._img_points), w, h,
        )
        return True

    def draw_corners(
        self,
        frame: np.ndarray,
        found: bool = True,
    ) -> np.ndarray:
        """Draw detected checkerboard corners on *frame* for visual feedback.

        Requires that the last call to :meth:`add_calibration_frame` was
        on the same frame.  If *found* is *False*, nothing is drawn.
        """
        if not found or not self._img_points:
            return frame
        cv2.drawChessboardCorners(
            frame, self._board_size, self._img_points[-1], found,
        )
        return frame

    # ------------------------------------------------------------------
    # Run calibration
    # ------------------------------------------------------------------

    def calibrate(self, min_frames: int = 10) -> Optional[IntrinsicCalibration]:
        """Run OpenCV camera calibration on collected frames.

        Returns the resulting :class:`IntrinsicCalibration` or *None* if
        too few frames have been collected.
        """
        if len(self._img_points) < min_frames:
            logger.warning(
                "Not enough calibration frames (%d < %d).",
                len(self._img_points), min_frames,
            )
            return None

        if self._image_size is None:
            logger.error("Image size unknown — cannot calibrate.")
            return None

        w, h = self._image_size
        rms, camera_matrix, dist_coeffs, _rvecs, _tvecs = cv2.calibrateCamera(
            self._obj_points,
            self._img_points,
            (w, h),
            None,
            None,
        )

        fx = float(camera_matrix[0, 0])
        fy = float(camera_matrix[1, 1])
        focal_avg = (fx + fy) / 2.0

        intrinsic = IntrinsicCalibration(
            camera_matrix=camera_matrix.tolist(),
            distortion_coefficients=dist_coeffs.flatten().tolist(),
            reprojection_error=round(float(rms), 4),
            image_width=w,
            image_height=h,
            focal_length_px=round(focal_avg, 2),
            status=CalibrationStatus.CALIBRATED,
            timestamp=time.time(),
        )

        self._intrinsic = intrinsic
        self._status = CalibrationStatus.CALIBRATED
        self._save_calibration(intrinsic)

        logger.info(
            "Camera calibrated — RMS error: %.4f, focal length: %.2f px.",
            rms, focal_avg,
        )
        return intrinsic

    # ------------------------------------------------------------------
    # Reprojection error (quality metric)
    # ------------------------------------------------------------------

    @property
    def reprojection_error(self) -> Optional[float]:
        if self._intrinsic is None:
            return None
        return self._intrinsic.reprojection_error

    # ------------------------------------------------------------------
    # Undistortion
    # ------------------------------------------------------------------

    def undistort(self, frame: np.ndarray) -> np.ndarray:
        """Remove lens distortion from *frame* using the calibration.

        Returns the original frame unchanged if uncalibrated.
        """
        if self._intrinsic is None or self._status != CalibrationStatus.CALIBRATED:
            return frame

        cam_mtx = np.array(self._intrinsic.camera_matrix, dtype=np.float64)
        dist = np.array(self._intrinsic.distortion_coefficients, dtype=np.float64)
        return cv2.undistort(frame, cam_mtx, dist)

    # ------------------------------------------------------------------
    # Focal-length helpers
    # ------------------------------------------------------------------

    def get_focal_length(self) -> Optional[float]:
        """Return calibrated focal length, or *None*."""
        if self._intrinsic is not None:
            return self._intrinsic.focal_length_px
        return None

    @staticmethod
    def estimate_focal_length_from_fov(
        frame_width: int,
        fov_degrees: float = 60.0,
    ) -> float:
        """Fallback focal-length estimate from assumed FOV.

        f = w / (2 × tan(FOV / 2))
        """
        fov_rad = math.radians(fov_degrees)
        half_tan = math.tan(fov_rad / 2.0)
        if half_tan < 1e-9:
            return float(frame_width)
        return frame_width / (2.0 * half_tan)

    # ------------------------------------------------------------------
    # Screen geometry
    # ------------------------------------------------------------------

    def set_screen_geometry(self, geometry: ScreenGeometry) -> None:
        """Persist screen geometry configuration."""
        self._calibration_dir.mkdir(parents=True, exist_ok=True)
        path = self._calibration_dir / "screen_geometry.json"
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(geometry), f, indent=2)
            logger.info("Screen geometry saved to %s", path)
        except OSError:
            logger.exception("Failed to save screen geometry.")

    def load_screen_geometry(self) -> Optional[ScreenGeometry]:
        """Load previously saved screen geometry."""
        path = self._calibration_dir / "screen_geometry.json"
        if not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ScreenGeometry(**data)
        except (OSError, json.JSONDecodeError, TypeError):
            logger.warning("Could not load screen geometry from %s", path)
            return None

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Discard all collected frames and calibration data."""
        self._obj_points.clear()
        self._img_points.clear()
        self._intrinsic = None
        self._status = CalibrationStatus.UNCALIBRATED
        self._image_size = None
        logger.info("Calibration reset.")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_calibration(self, cal: IntrinsicCalibration) -> None:
        self._calibration_dir.mkdir(parents=True, exist_ok=True)
        path = self._calibration_dir / _INTRINSIC_FILE
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(cal), f, indent=2)
            logger.info("Intrinsic calibration saved to %s", path)
        except OSError:
            logger.exception("Failed to save intrinsic calibration to %s", path)

    def _load_calibration(self) -> None:
        path = self._calibration_dir / _INTRINSIC_FILE
        if not path.is_file():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._intrinsic = IntrinsicCalibration(**data)
            if self._intrinsic.status == CalibrationStatus.CALIBRATED:
                self._status = CalibrationStatus.CALIBRATED
            logger.info("Loaded intrinsic calibration from %s", path)
        except (OSError, json.JSONDecodeError, TypeError):
            logger.warning("Could not load intrinsic calibration from %s", path)

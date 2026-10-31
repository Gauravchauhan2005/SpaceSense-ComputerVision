"""
SpaceSense AI — Distance Estimation

Estimates real-world distance (in centimetres) from the camera to faces
and hands using the pinhole-camera model:

    Z  =  (f × W) / w

where *f* is focal length in pixels, *W* is known real-world size, and
*w* is the measured size in pixels.  Supports user-calibrated reference
distances, screen-geometry calibration, and closest-object ranking.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from backend.models import (
    ClosestObjectResult,
    DistanceResult,
    FaceTrackingResult,
    HandTrackingResult,
    ReferenceCalibration,
    ScreenGeometry,
    SingleFaceResult,
    SingleHandResult,
)

logger = logging.getLogger(__name__)

# Physical reference values (mm → cm used internally)
_AVG_INTER_PUPILLARY_CM: float = 6.3      # average IPD
_AVG_FACE_WIDTH_CM: float = 15.0           # ear-to-ear approximation
_AVG_PALM_WIDTH_CM: float = 8.5            # index MCP → pinky MCP

# Default calibration file location
_DEFAULT_CALIBRATION_DIR = Path("calibration")
_REF_CALIB_FILE = "reference_calibration.json"
_SCREEN_GEOM_FILE = "screen_geometry.json"


class DistanceEstimator:
    """Estimate distances from the camera to tracked objects.

    Parameters
    ----------
    focal_length_px : float or None
        Known or estimated focal length in pixels.  If *None*, a rough
        estimate is derived from the frame width using a typical webcam
        FOV of ~60°.
    frame_width : int
        Frame width in pixels (used for focal-length fallback).
    calibration_dir : str or Path
        Directory for loading / saving calibration JSON files.
    """

    def __init__(
        self,
        focal_length_px: Optional[float] = None,
        frame_width: int = 640,
        calibration_dir: str | Path = _DEFAULT_CALIBRATION_DIR,
    ) -> None:
        self._calibration_dir = Path(calibration_dir)
        self._frame_width = frame_width

        # Focal length
        if focal_length_px is not None:
            self._focal_length_px = focal_length_px
        else:
            self._focal_length_px = self._estimate_focal_length(frame_width)

        # Reference calibration (loaded lazily or set via API)
        self._ref_calibration: Optional[ReferenceCalibration] = None
        self._screen_geometry: Optional[ScreenGeometry] = None

        # Try to load persisted calibration
        self._load_reference_calibration()
        self._load_screen_geometry()

    # ------------------------------------------------------------------
    # Focal-length fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_focal_length(
        frame_width: int,
        fov_degrees: float = 60.0,
    ) -> float:
        """Estimate focal length in pixels from horizontal FOV.

        f = w / (2 × tan(FOV / 2))
        """
        fov_rad = math.radians(fov_degrees)
        half_tan = math.tan(fov_rad / 2.0)
        if half_tan < 1e-9:
            return float(frame_width)
        return frame_width / (2.0 * half_tan)

    @property
    def focal_length_px(self) -> float:
        return self._focal_length_px

    @focal_length_px.setter
    def focal_length_px(self, value: float) -> None:
        self._focal_length_px = value

    @property
    def is_calibrated(self) -> bool:
        """Whether reference distance calibration is active."""
        return self._ref_calibration is not None and self._ref_calibration.scale_factor is not None

    @property
    def ref_calibration(self) -> Optional[ReferenceCalibration]:
        return self._ref_calibration

    def reset_calibration(self) -> None:
        """Clear reference calibration and restore default focal length."""
        self._ref_calibration = None
        self._focal_length_px = self._estimate_focal_length(self._frame_width)
        ref_file = self._calibration_dir / _REF_CALIB_FILE
        if ref_file.is_file():
            try:
                ref_file.unlink()
                logger.info("Deleted reference calibration file %s", ref_file)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Face distance
    # ------------------------------------------------------------------

    def estimate_face_distance(
        self,
        face_result: FaceTrackingResult,
        use_inter_eye: bool = True,
    ) -> Optional[DistanceResult]:
        """Estimate the distance to the primary face.

        Uses inter-pupillary distance by default; falls back to face
        width if unavailable.  Returns *None* when no face is detected.
        """
        if not face_result.detected or face_result.primary_face is None:
            return None

        face = face_result.primary_face
        return self._face_distance_from_single(face, use_inter_eye)

    def _face_distance_from_single(
        self,
        face: SingleFaceResult,
        use_inter_eye: bool = True,
    ) -> Optional[DistanceResult]:
        """Distance estimate for a single face."""
        pixel_width: Optional[float] = None
        real_width_cm: float = _AVG_FACE_WIDTH_CM
        label = "face (width)"

        if use_inter_eye and face.inter_eye_distance_px is not None:
            pixel_width = face.inter_eye_distance_px
            real_width_cm = _AVG_INTER_PUPILLARY_CM
            label = "face (IPD)"
        elif face.face_width_px is not None:
            pixel_width = face.face_width_px
        else:
            return None

        if pixel_width is None or pixel_width < 1e-3:
            return None

        # Apply reference-calibration scale factor if available
        f = self._effective_focal_length_face()
        distance_cm = (f * real_width_cm) / pixel_width

        calibrated = self._ref_calibration is not None
        confidence = self._compute_confidence(
            pixel_width, calibrated, face.confidence,
        )

        return DistanceResult(
            distance_cm=round(distance_cm, 1),
            object_label=label,
            confidence=round(confidence, 3),
            calibrated=calibrated,
        )

    def _effective_focal_length_face(self) -> float:
        """Return calibration-adjusted focal length for face estimation."""
        if (
            self._ref_calibration is not None
            and self._ref_calibration.scale_factor is not None
        ):
            return self._focal_length_px * self._ref_calibration.scale_factor
        return self._focal_length_px

    # ------------------------------------------------------------------
    # Hand distance
    # ------------------------------------------------------------------

    def estimate_hand_distance(
        self,
        hand_result: HandTrackingResult,
        which: str = "any",
    ) -> Optional[DistanceResult]:
        """Estimate the distance to a detected hand.

        Parameters
        ----------
        hand_result : HandTrackingResult
        which : str
            ``"left"``, ``"right"``, or ``"any"`` (first available).
        """
        hand: Optional[SingleHandResult] = None
        if which == "left" and hand_result.left_hand is not None:
            hand = hand_result.left_hand
        elif which == "right" and hand_result.right_hand is not None:
            hand = hand_result.right_hand
        elif which == "any" and hand_result.hands:
            hand = hand_result.hands[0]

        if hand is None:
            return None

        return self._hand_distance_from_single(hand)

    def _hand_distance_from_single(
        self,
        hand: SingleHandResult,
    ) -> Optional[DistanceResult]:
        """Distance estimate for a single hand using palm width."""
        if hand.palm_width_px is None or hand.palm_width_px < 1e-3:
            return None

        f = self._effective_focal_length_hand()
        distance_cm = (f * _AVG_PALM_WIDTH_CM) / hand.palm_width_px

        calibrated = self._ref_calibration is not None
        confidence = self._compute_confidence(
            hand.palm_width_px, calibrated, hand.confidence,
        )

        return DistanceResult(
            distance_cm=round(distance_cm, 1),
            object_label=f"hand ({hand.handedness.value})",
            confidence=round(confidence, 3),
            calibrated=calibrated,
        )

    def _effective_focal_length_hand(self) -> float:
        """Return calibration-adjusted focal length for hand estimation."""
        if (
            self._ref_calibration is not None
            and self._ref_calibration.scale_factor is not None
        ):
            return self._focal_length_px * self._ref_calibration.scale_factor
        return self._focal_length_px

    # ------------------------------------------------------------------
    # Closest object
    # ------------------------------------------------------------------

    def find_closest_object(
        self,
        face_result: FaceTrackingResult,
        hand_result: HandTrackingResult,
    ) -> ClosestObjectResult:
        """Compare face / left_hand / right_hand distances and return
        the closest.
        """
        distances: dict[str, Optional[float]] = {}

        face_dist = self.estimate_face_distance(face_result)
        distances["face"] = face_dist.distance_cm if face_dist else None

        for which in ("left", "right"):
            hand_dist = self.estimate_hand_distance(hand_result, which=which)
            distances[f"{which}_hand"] = hand_dist.distance_cm if hand_dist else None

        # Find minimum non-None distance
        valid = {k: v for k, v in distances.items() if v is not None}
        if not valid:
            return ClosestObjectResult(all_distances=distances)

        closest_label = min(valid, key=lambda k: valid[k])  # type: ignore[arg-type]
        return ClosestObjectResult(
            label=closest_label,
            distance_cm=valid[closest_label],
            all_distances=distances,
        )

    # ------------------------------------------------------------------
    # Screen distance (when screen geometry is calibrated)
    # ------------------------------------------------------------------

    def estimate_screen_distance(
        self,
        face_result: FaceTrackingResult,
    ) -> Optional[DistanceResult]:
        """Estimate distance from the user's face to the *screen*.

        This subtracts the camera-to-face distance from the known
        camera-to-screen offset if screen geometry is calibrated.
        For a typical laptop, the camera sits on the screen bezel so
        the screen distance ≈ face distance.
        """
        face_dist = self.estimate_face_distance(face_result)
        if face_dist is None or face_dist.distance_cm is None:
            return None

        # If screen geometry is set, adjust for camera offset
        # (usually the offset is negligible for laptop cams)
        return DistanceResult(
            distance_cm=face_dist.distance_cm,
            object_label="screen",
            confidence=face_dist.confidence,
            calibrated=face_dist.calibrated,
        )

    # ------------------------------------------------------------------
    # Reference-distance calibration
    # ------------------------------------------------------------------

    def calibrate_reference(
        self,
        reference_distance_cm: float,
        face_result: Optional[FaceTrackingResult] = None,
        hand_result: Optional[HandTrackingResult] = None,
    ) -> ReferenceCalibration:
        """Perform a reference-distance calibration.

        The user stands at a known distance and the system records the
        pixel measurements, then computes a scale factor that corrects
        future estimates.
        """
        measured_face_width: Optional[float] = None
        measured_inter_eye: Optional[float] = None
        measured_palm_width: Optional[float] = None

        if face_result and face_result.primary_face:
            face = face_result.primary_face
            measured_face_width = face.face_width_px
            measured_inter_eye = face.inter_eye_distance_px

        if hand_result and hand_result.hands:
            measured_palm_width = hand_result.hands[0].palm_width_px

        # Calculate scale factor using inter-eye distance as primary
        scale_factor: Optional[float] = None
        if measured_inter_eye and measured_inter_eye > 0:
            # Expected pixel width at this distance:
            # w_expected = (f * W) / D
            expected_px = (self._focal_length_px * _AVG_INTER_PUPILLARY_CM) / reference_distance_cm
            if expected_px > 0:
                scale_factor = measured_inter_eye / expected_px
        elif measured_face_width and measured_face_width > 0:
            expected_px = (self._focal_length_px * _AVG_FACE_WIDTH_CM) / reference_distance_cm
            if expected_px > 0:
                scale_factor = measured_face_width / expected_px
        elif measured_palm_width and measured_palm_width > 0:
            expected_px = (self._focal_length_px * _AVG_PALM_WIDTH_CM) / reference_distance_cm
            if expected_px > 0:
                scale_factor = measured_palm_width / expected_px

        cal = ReferenceCalibration(
            reference_distance_cm=reference_distance_cm,
            measured_face_width_px=measured_face_width,
            measured_inter_eye_px=measured_inter_eye,
            measured_palm_width_px=measured_palm_width,
            focal_length_estimated=self._focal_length_px,
            scale_factor=scale_factor,
        )

        self._ref_calibration = cal
        self._save_reference_calibration(cal)
        logger.info("Reference calibration saved (scale_factor=%.4f).",
                     scale_factor or 0.0)
        return cal

    # ------------------------------------------------------------------
    # Screen geometry calibration
    # ------------------------------------------------------------------

    def set_screen_geometry(self, geometry: ScreenGeometry) -> None:
        """Set physical screen dimensions and camera offset."""
        self._screen_geometry = geometry
        self._save_screen_geometry(geometry)

    def get_screen_geometry(self) -> Optional[ScreenGeometry]:
        return self._screen_geometry

    # ------------------------------------------------------------------
    # Confidence heuristic
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_confidence(
        pixel_measurement: float,
        is_calibrated: bool,
        tracking_confidence: float,
    ) -> float:
        """Simple confidence heuristic combining calibration status and
        tracking quality.

        - Calibrated measurements start at 0.8; uncalibrated at 0.4.
        - Larger pixel measurements → higher confidence (less noise).
        - Multiplied by tracking confidence.
        """
        base = 0.8 if is_calibrated else 0.4
        # Size factor: approaches 1.0 for pixel_measurement >= 100
        size_factor = min(1.0, pixel_measurement / 100.0)
        return min(1.0, base * size_factor * max(0.1, tracking_confidence))

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _save_reference_calibration(self, cal: ReferenceCalibration) -> None:
        self._calibration_dir.mkdir(parents=True, exist_ok=True)
        path = self._calibration_dir / _REF_CALIB_FILE
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(cal), f, indent=2)
        except OSError:
            logger.exception("Failed to save reference calibration to %s", path)

    def _load_reference_calibration(self) -> None:
        path = self._calibration_dir / _REF_CALIB_FILE
        if not path.is_file():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._ref_calibration = ReferenceCalibration(**data)
            logger.info("Loaded reference calibration from %s", path)
        except (OSError, json.JSONDecodeError, TypeError):
            logger.warning("Could not load reference calibration from %s", path)

    def _save_screen_geometry(self, geom: ScreenGeometry) -> None:
        self._calibration_dir.mkdir(parents=True, exist_ok=True)
        path = self._calibration_dir / _SCREEN_GEOM_FILE
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(asdict(geom), f, indent=2)
        except OSError:
            logger.exception("Failed to save screen geometry to %s", path)

    def _load_screen_geometry(self) -> None:
        path = self._calibration_dir / _SCREEN_GEOM_FILE
        if not path.is_file():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._screen_geometry = ScreenGeometry(**data)
            logger.info("Loaded screen geometry from %s", path)
        except (OSError, json.JSONDecodeError, TypeError):
            logger.warning("Could not load screen geometry from %s", path)

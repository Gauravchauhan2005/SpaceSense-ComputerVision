"""
SpaceSense AI — Face Landmark Detection

Uses MediaPipe Face Landmarker (Tasks API) to detect up to 2 faces and extract
landmarks per face, computing key derived metrics (bounding box, inter-eye distance,
face width, etc.).
"""

from __future__ import annotations

import logging
import math
import os
from pathlib import Path
from typing import Optional, Sequence, Tuple

import cv2
import numpy as np

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from backend.models import (
    BoundingBox,
    FaceLandmarks,
    FaceTrackingResult,
    Point2D,
    Point3D,
    SingleFaceResult,
)

logger = logging.getLogger(__name__)

# Key landmark indices (MediaPipe Face Mesh canonical)
_NOSE_TIP = 1
_LEFT_EYE_CENTER = 159
_RIGHT_EYE_CENTER = 386
_CHIN = 152
_FOREHEAD = 10
_LEFT_EAR = 234
_RIGHT_EAR = 454

_DEFAULT_MODEL_PATH = Path("models") / "face_landmarker.task"


class FaceTracker:
    """Detect and track facial landmarks using MediaPipe FaceLandmarker.

    Parameters
    ----------
    max_faces : int
        Maximum number of faces to detect (1 or 2).
    min_detection_confidence : float
        Minimum confidence for initial detection.
    min_tracking_confidence : float
        Minimum confidence for landmark tracking.
    model_path : str or Path or None
        Path to face_landmarker.task bundle.
    """

    def __init__(
        self,
        max_faces: int = 2,
        min_detection_confidence: float = 0.35,
        min_tracking_confidence: float = 0.35,
        model_path: Optional[str | Path] = None,
    ) -> None:
        self._max_faces = max_faces
        
        # Locate model file
        path_to_try = Path(model_path) if model_path else _DEFAULT_MODEL_PATH
        if not path_to_try.is_file():
            # Try finding relative to workspace
            alt_path = Path(__file__).resolve().parent.parent.parent / "models" / "face_landmarker.task"
            if alt_path.is_file():
                path_to_try = alt_path

        if not path_to_try.is_file():
            raise FileNotFoundError(f"MediaPipe Face Landmarker model not found at {path_to_try}")

        base_options = python.BaseOptions(model_asset_path=str(path_to_try))
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=max_faces,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

    # ------------------------------------------------------------------
    # Core detection
    # ------------------------------------------------------------------

    def process(self, frame: np.ndarray) -> FaceTrackingResult:
        """Run face landmark inference on a BGR frame.

        Returns a FaceTrackingResult with detected faces.
        """
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        
        try:
            mp_result = self._landmarker.detect(mp_image)
        except Exception as exc:
            logger.error("FaceLandmarker error: %s", exc)
            return FaceTrackingResult(detected=False, face_count=0)

        if not mp_result.face_landmarks:
            return FaceTrackingResult(detected=False, face_count=0)

        faces: list[SingleFaceResult] = []
        for face_lms in mp_result.face_landmarks:
            single = self._extract_face(face_lms, w, h)
            faces.append(single)

        primary = faces[0] if faces else None
        return FaceTrackingResult(
            detected=True,
            face_count=len(faces),
            faces=faces,
            primary_face=primary,
        )

    # ------------------------------------------------------------------
    # Per-face extraction
    # ------------------------------------------------------------------

    def _extract_face(
        self,
        face_lms: Sequence[object],
        frame_w: int,
        frame_h: int,
    ) -> SingleFaceResult:
        """Convert raw MediaPipe landmarks to SingleFaceResult."""
        all_pts: list[Point3D] = []
        for lm in face_lms:
            all_pts.append(Point3D(
                x=lm.x * frame_w,
                y=lm.y * frame_h,
                z=getattr(lm, "z", 0.0),
            ))

        def _pt(idx: int) -> Optional[Point3D]:
            if idx < len(all_pts):
                return all_pts[idx]
            return None

        key_lms = FaceLandmarks(
            nose_tip=_pt(_NOSE_TIP),
            left_eye_center=_pt(_LEFT_EYE_CENTER),
            right_eye_center=_pt(_RIGHT_EYE_CENTER),
            chin=_pt(_CHIN),
            forehead=_pt(_FOREHEAD),
            left_ear=_pt(_LEFT_EAR),
            right_ear=_pt(_RIGHT_EAR),
            all_landmarks=all_pts,
        )

        bbox = self._compute_bbox(all_pts)
        center = bbox.center if bbox else None
        inter_eye = self._inter_eye_distance(key_lms)
        face_width = self._face_width(key_lms)

        return SingleFaceResult(
            landmarks=key_lms,
            bounding_box=bbox,
            center=center,
            inter_eye_distance_px=inter_eye,
            face_width_px=face_width,
            confidence=1.0,
        )

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_bbox(pts: Sequence[Point3D]) -> Optional[BoundingBox]:
        if not pts:
            return None
        xs = [p.x for p in pts]
        ys = [p.y for p in pts]
        return BoundingBox(
            x_min=min(xs), y_min=min(ys),
            x_max=max(xs), y_max=max(ys),
        )

    @staticmethod
    def _inter_eye_distance(lms: FaceLandmarks) -> Optional[float]:
        le, re = lms.left_eye_center, lms.right_eye_center
        if le is None or re is None:
            return None
        return math.hypot(le.x - re.x, le.y - re.y)

    @staticmethod
    def _face_width(lms: FaceLandmarks) -> Optional[float]:
        le, re = lms.left_ear, lms.right_ear
        if le is None or re is None:
            return None
        return math.hypot(le.x - re.x, le.y - re.y)

    # ------------------------------------------------------------------
    # Drawing utilities
    # ------------------------------------------------------------------

    def draw_landmarks(
        self,
        frame: np.ndarray,
        result: FaceTrackingResult,
        color: Tuple[int, int, int] = (0, 255, 0),
        radius: int = 1,
        thickness: int = 1,
    ) -> np.ndarray:
        """Draw all facial landmarks onto frame (in-place) and return it."""
        for face in result.faces:
            for pt in face.landmarks.all_landmarks:
                cv2.circle(frame, (int(pt.x), int(pt.y)), radius, color, thickness)
        return frame

    def draw_bounding_boxes(
        self,
        frame: np.ndarray,
        result: FaceTrackingResult,
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2,
    ) -> np.ndarray:
        """Draw face bounding boxes onto frame (in-place) and return it."""
        for face in result.faces:
            if face.bounding_box is not None:
                bb = face.bounding_box
                cv2.rectangle(
                    frame,
                    (int(bb.x_min), int(bb.y_min)),
                    (int(bb.x_max), int(bb.y_max)),
                    color,
                    thickness,
                )
        return frame

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release MediaPipe resources."""
        if hasattr(self, "_landmarker") and self._landmarker:
            self._landmarker.close()

    def __enter__(self) -> "FaceTracker":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

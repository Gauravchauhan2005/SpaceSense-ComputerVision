"""
SpaceSense AI — Hand Landmark Detection

Uses MediaPipe Hand Landmarker (Tasks API) to detect up to 2 hands and extract
all 21 landmarks per hand, computing derived metrics (palm center, fingertip
positions, bounding box, palm width, etc.).
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
    Handedness,
    HandTrackingResult,
    Point2D,
    Point3D,
    SingleHandResult,
)

logger = logging.getLogger(__name__)

# Landmark indices
_WRIST = 0
_THUMB_TIP = 4
_INDEX_TIP = 8
_MIDDLE_TIP = 12
_RING_TIP = 16
_PINKY_TIP = 20

_INDEX_MCP = 5
_MIDDLE_MCP = 9
_RING_MCP = 13
_PINKY_MCP = 17

_FINGERTIP_NAMES: dict[int, str] = {
    _THUMB_TIP: "thumb",
    _INDEX_TIP: "index",
    _MIDDLE_TIP: "middle",
    _RING_TIP: "ring",
    _PINKY_TIP: "pinky",
}

# MediaPipe hand connections for skeleton drawing
_HAND_CONNECTIONS: list[Tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # index
    (0, 9), (9, 10), (10, 11), (11, 12),   # middle
    (0, 13), (13, 14), (14, 15), (15, 16), # ring
    (0, 17), (17, 18), (18, 19), (19, 20), # pinky
    (5, 9), (9, 13), (13, 17),             # palm
]

_DEFAULT_MODEL_PATH = Path("models") / "hand_landmarker.task"


class HandTracker:
    """Detect and track hand landmarks using MediaPipe HandLandmarker.

    Parameters
    ----------
    max_hands : int
        Maximum number of hands to detect (1 or 2).
    min_detection_confidence : float
        Minimum confidence for initial detection.
    min_tracking_confidence : float
        Minimum confidence for landmark tracking.
    model_path : str or Path or None
        Path to hand_landmarker.task bundle.
    """

    def __init__(
        self,
        max_hands: int = 2,
        min_detection_confidence: float = 0.35,
        min_tracking_confidence: float = 0.35,
        model_path: Optional[str | Path] = None,
        flip_handedness: bool = True,
    ) -> None:
        self._max_hands = max_hands
        self._flip_handedness = flip_handedness

        # Locate model file
        path_to_try = Path(model_path) if model_path else _DEFAULT_MODEL_PATH
        if not path_to_try.is_file():
            alt_path = Path(__file__).resolve().parent.parent.parent / "models" / "hand_landmarker.task"
            if alt_path.is_file():
                path_to_try = alt_path

        if not path_to_try.is_file():
            raise FileNotFoundError(f"MediaPipe Hand Landmarker model not found at {path_to_try}")

        base_options = python.BaseOptions(model_asset_path=str(path_to_try))
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_hands=max_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_hand_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.HandLandmarker.create_from_options(options)

    @property
    def flip_handedness(self) -> bool:
        """Whether handedness is inverted to account for selfie / mirror mode."""
        return self._flip_handedness

    @flip_handedness.setter
    def flip_handedness(self, value: bool) -> None:
        self._flip_handedness = value

    # ------------------------------------------------------------------
    # Core detection
    # ------------------------------------------------------------------

    def process(self, frame: np.ndarray) -> HandTrackingResult:
        """Run hand inference on a BGR frame.

        Returns HandTrackingResult with detected hands.
        """
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        try:
            mp_result = self._landmarker.detect(mp_image)
        except Exception as exc:
            logger.error("HandLandmarker error: %s", exc)
            return HandTrackingResult(detected=False, hand_count=0)

        if not mp_result.hand_landmarks:
            return HandTrackingResult(detected=False, hand_count=0)

        hands: list[SingleHandResult] = []
        left_hand: Optional[SingleHandResult] = None
        right_hand: Optional[SingleHandResult] = None

        for idx, hand_lms in enumerate(mp_result.hand_landmarks):
            hand_label = Handedness.RIGHT
            hand_conf = 1.0

            if mp_result.handedness and idx < len(mp_result.handedness):
                categories = mp_result.handedness[idx]
                if categories:
                    label_str = categories[0].category_name  # "Left" or "Right"
                    hand_conf = categories[0].score
                    if self._flip_handedness:
                        # In mirrored / selfie view, MediaPipe's "Left" is the user's physical Right hand
                        hand_label = Handedness.RIGHT if label_str == "Left" else Handedness.LEFT
                    else:
                        hand_label = Handedness.LEFT if label_str == "Left" else Handedness.RIGHT

            single = self._extract_hand(hand_lms, w, h, hand_label, hand_conf)
            hands.append(single)

            if hand_label == Handedness.LEFT and left_hand is None:
                left_hand = single
            elif hand_label == Handedness.RIGHT and right_hand is None:
                right_hand = single

        return HandTrackingResult(
            detected=True,
            hand_count=len(hands),
            hands=hands,
            left_hand=left_hand,
            right_hand=right_hand,
        )

    # ------------------------------------------------------------------
    # Per-hand extraction
    # ------------------------------------------------------------------

    def _extract_hand(
        self,
        hand_lms: Sequence[object],
        frame_w: int,
        frame_h: int,
        handedness: Handedness,
        confidence: float,
    ) -> SingleHandResult:
        """Convert raw MediaPipe landmarks to SingleHandResult."""
        pts: list[Point3D] = []
        for lm in hand_lms:
            pts.append(Point3D(
                x=lm.x * frame_w,
                y=lm.y * frame_h,
                z=getattr(lm, "z", 0.0),
            ))

        hand_center = self._compute_hand_center(pts)
        palm_center = self._compute_palm_center(pts)
        fingertips = self._compute_fingertips(pts)
        bbox = self._compute_bbox(pts)
        palm_width = self._compute_palm_width(pts)

        return SingleHandResult(
            handedness=handedness,
            landmarks=pts,
            hand_center=hand_center,
            palm_center=palm_center,
            fingertip_positions=fingertips,
            bounding_box=bbox,
            palm_width_px=palm_width,
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_hand_center(pts: list[Point3D]) -> Optional[Point2D]:
        """Average of all 21 landmarks."""
        if not pts:
            return None
        avg_x = sum(p.x for p in pts) / len(pts)
        avg_y = sum(p.y for p in pts) / len(pts)
        return Point2D(x=avg_x, y=avg_y)

    @staticmethod
    def _compute_palm_center(pts: list[Point3D]) -> Optional[Point2D]:
        """Average of wrist, index_mcp, middle_mcp, pinky_mcp."""
        indices = [_WRIST, _INDEX_MCP, _MIDDLE_MCP, _PINKY_MCP]
        if len(pts) < max(indices) + 1:
            return None
        selected = [pts[i] for i in indices]
        avg_x = sum(p.x for p in selected) / len(selected)
        avg_y = sum(p.y for p in selected) / len(selected)
        return Point2D(x=avg_x, y=avg_y)

    @staticmethod
    def _compute_fingertips(pts: list[Point3D]) -> dict[str, Point2D]:
        """Extract the 5 fingertip positions."""
        tips: dict[str, Point2D] = {}
        for idx, name in _FINGERTIP_NAMES.items():
            if idx < len(pts):
                tips[name] = Point2D(x=pts[idx].x, y=pts[idx].y)
        return tips

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
    def _compute_palm_width(pts: list[Point3D]) -> Optional[float]:
        """Distance from INDEX_MCP to PINKY_MCP."""
        if len(pts) < max(_INDEX_MCP, _PINKY_MCP) + 1:
            return None
        a, b = pts[_INDEX_MCP], pts[_PINKY_MCP]
        return math.hypot(a.x - b.x, a.y - b.y)

    # ------------------------------------------------------------------
    # Drawing utilities
    # ------------------------------------------------------------------

    def draw_skeleton(
        self,
        frame: np.ndarray,
        result: HandTrackingResult,
        color: Tuple[int, int, int] = (0, 255, 255),
        thickness: int = 2,
    ) -> np.ndarray:
        """Draw hand skeleton connections onto frame (in-place)."""
        for hand in result.hands:
            pts = hand.landmarks
            for i, j in _HAND_CONNECTIONS:
                if i < len(pts) and j < len(pts):
                    p1 = (int(pts[i].x), int(pts[i].y))
                    p2 = (int(pts[j].x), int(pts[j].y))
                    cv2.line(frame, p1, p2, color, thickness)
        return frame

    def draw_landmarks(
        self,
        frame: np.ndarray,
        result: HandTrackingResult,
        color: Tuple[int, int, int] = (255, 0, 0),
        radius: int = 3,
        show_indices: bool = False,
    ) -> np.ndarray:
        """Draw landmark dots (optionally with index labels) onto frame."""
        for hand in result.hands:
            for idx, pt in enumerate(hand.landmarks):
                pos = (int(pt.x), int(pt.y))
                cv2.circle(frame, pos, radius, color, -1)
                if show_indices:
                    cv2.putText(
                        frame, str(idx), (pos[0] + 4, pos[1] - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1,
                    )
        return frame

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release MediaPipe resources."""
        if hasattr(self, "_landmarker") and self._landmarker:
            self._landmarker.close()

    def __enter__(self) -> "HandTracker":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

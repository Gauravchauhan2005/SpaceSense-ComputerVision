"""
SpaceSense AI — Shared Data Models

Dataclasses for internal data transfer and Pydantic models for API-facing contracts.
All spatial coordinates are in pixels unless otherwise noted.
All distances are in centimeters when calibrated.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CameraStatus(str, Enum):
    """Current state of the camera device."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    INITIALIZING = "initializing"


class CalibrationStatus(str, Enum):
    """State of camera / distance calibration."""
    UNCALIBRATED = "uncalibrated"
    IN_PROGRESS = "in_progress"
    CALIBRATED = "calibrated"


class Handedness(str, Enum):
    """Which hand was detected."""
    LEFT = "Left"
    RIGHT = "Right"


# ---------------------------------------------------------------------------
# Basic geometry helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Point2D:
    """An (x, y) point in pixel coordinates."""
    x: float
    y: float


@dataclass(frozen=True)
class Point3D:
    """An (x, y, z) point — z is MediaPipe's normalised depth."""
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class BoundingBox:
    """Axis-aligned bounding box in pixel coordinates."""
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    @property
    def center(self) -> Point2D:
        return Point2D(
            x=(self.x_min + self.x_max) / 2.0,
            y=(self.y_min + self.y_max) / 2.0,
        )


# ---------------------------------------------------------------------------
# Face tracking result
# ---------------------------------------------------------------------------

@dataclass
class FaceLandmarks:
    """Key facial landmarks extracted from MediaPipe FaceMesh."""
    nose_tip: Optional[Point3D] = None          # landmark 1
    left_eye_center: Optional[Point3D] = None   # landmark 159
    right_eye_center: Optional[Point3D] = None  # landmark 386
    chin: Optional[Point3D] = None              # landmark 152
    forehead: Optional[Point3D] = None          # landmark 10
    left_ear: Optional[Point3D] = None          # landmark 234
    right_ear: Optional[Point3D] = None         # landmark 454
    all_landmarks: list[Point3D] = field(default_factory=list)


@dataclass
class SingleFaceResult:
    """Tracking result for one detected face."""
    landmarks: FaceLandmarks
    bounding_box: Optional[BoundingBox] = None
    center: Optional[Point2D] = None
    inter_eye_distance_px: Optional[float] = None
    face_width_px: Optional[float] = None
    confidence: float = 0.0


@dataclass
class FaceTrackingResult:
    """Aggregated face-tracking output for a single frame."""
    detected: bool = False
    face_count: int = 0
    faces: list[SingleFaceResult] = field(default_factory=list)
    primary_face: Optional[SingleFaceResult] = None
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Hand tracking result
# ---------------------------------------------------------------------------

@dataclass
class SingleHandResult:
    """Tracking result for one detected hand."""
    handedness: Handedness = Handedness.RIGHT
    landmarks: list[Point3D] = field(default_factory=list)
    hand_center: Optional[Point2D] = None
    palm_center: Optional[Point2D] = None
    fingertip_positions: dict[str, Point2D] = field(default_factory=dict)
    bounding_box: Optional[BoundingBox] = None
    palm_width_px: Optional[float] = None
    confidence: float = 0.0


@dataclass
class HandTrackingResult:
    """Aggregated hand-tracking output for a single frame."""
    detected: bool = False
    hand_count: int = 0
    hands: list[SingleHandResult] = field(default_factory=list)
    left_hand: Optional[SingleHandResult] = None
    right_hand: Optional[SingleHandResult] = None
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Unified frame result
# ---------------------------------------------------------------------------

@dataclass
class FrameResult:
    """Complete processing output for one video frame."""
    frame_number: int = 0
    face_result: FaceTrackingResult = field(default_factory=FaceTrackingResult)
    hand_result: HandTrackingResult = field(default_factory=HandTrackingResult)
    processing_time_ms: float = 0.0
    fps: float = 0.0
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Distance estimation
# ---------------------------------------------------------------------------

@dataclass
class DistanceResult:
    """Estimated distance for a single tracked object."""
    distance_cm: Optional[float] = None
    object_label: str = ""
    confidence: float = 0.0
    calibrated: bool = False


@dataclass
class ClosestObjectResult:
    """Which tracked object is closest to the camera."""
    label: str = ""
    distance_cm: Optional[float] = None
    all_distances: dict[str, Optional[float]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Calibration data (persistence)
# ---------------------------------------------------------------------------

@dataclass
class ReferenceCalibration:
    """Data captured during a reference-distance calibration step."""
    reference_distance_cm: float = 100.0
    measured_face_width_px: Optional[float] = None
    measured_inter_eye_px: Optional[float] = None
    measured_palm_width_px: Optional[float] = None
    focal_length_estimated: Optional[float] = None
    scale_factor: Optional[float] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class ScreenGeometry:
    """Physical screen and camera placement information."""
    screen_width_cm: float = 34.5
    screen_height_cm: float = 19.4
    camera_offset_x_cm: float = 0.0   # horizontal offset from screen center
    camera_offset_y_cm: float = 0.0   # vertical offset above top edge


@dataclass
class IntrinsicCalibration:
    """Camera intrinsic parameters from checkerboard calibration."""
    camera_matrix: list[list[float]] = field(default_factory=list)
    distortion_coefficients: list[float] = field(default_factory=list)
    reprojection_error: float = 0.0
    image_width: int = 0
    image_height: int = 0
    focal_length_px: Optional[float] = None
    status: CalibrationStatus = CalibrationStatus.UNCALIBRATED
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# API-facing Pydantic models
# ---------------------------------------------------------------------------

class CameraInfoResponse(BaseModel):
    """Camera information returned via API."""
    device_index: int = Field(default=0, description="Camera device index")
    resolution_width: int = Field(default=640, description="Frame width in pixels")
    resolution_height: int = Field(default=480, description="Frame height in pixels")
    fps: float = Field(default=0.0, description="Current measured FPS")
    status: CameraStatus = Field(default=CameraStatus.DISCONNECTED)


class ErgonomicState(str, Enum):
    """Ergonomic proximity classification."""
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Motion / Speed helpers
# ---------------------------------------------------------------------------

@dataclass
class SpeedStats:
    """Speed statistics over a motion analysis window."""
    current: float = 0.0
    average: float = 0.0
    max: float = 0.0
    min: float = 0.0


@dataclass
class MotionResult:
    """Result of motion analysis for a tracked point."""
    velocity: float = 0.0
    acceleration: float = 0.0
    direction_deg: float = 0.0
    trajectory: list["Point2D"] = field(default_factory=list)
    cumulative_distance: float = 0.0
    speed_stats: SpeedStats = field(default_factory=SpeedStats)


# ---------------------------------------------------------------------------
# Ergonomic status
# ---------------------------------------------------------------------------

@dataclass
class ErgonomicStatus:
    """Snapshot of the ergonomic monitor state."""
    state: ErgonomicState = ErgonomicState.NORMAL
    face_distance: Optional[float] = None
    time_in_state: float = 0.0
    warning_count: int = 0
    critical_count: int = 0


# ---------------------------------------------------------------------------
# API-facing Pydantic models
# ---------------------------------------------------------------------------

class CalibrationRequest(BaseModel):
    """Request body for reference-distance calibration."""
    reference_distance_cm: float = Field(
        ..., gt=0, description="Known distance from camera in cm"
    )


class CalibrationResponse(BaseModel):
    """Result of a calibration operation."""
    status: CalibrationStatus
    reprojection_error: Optional[float] = None
    focal_length_px: Optional[float] = None
    message: str = ""

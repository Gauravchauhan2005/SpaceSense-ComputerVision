"""
SpaceSense AI — REST API Routes

Provides all HTTP endpoints for camera control, calibration,
session management, evaluation, settings, and tracking status.
"""

from __future__ import annotations

import csv
import io
import time
from enum import Enum
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    pass

# ────────────────────────────────────────────────────────────────────
# Pydantic v2 Models — Request / Response
# ────────────────────────────────────────────────────────────────────


# ── Health ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    uptime_seconds: float


# ── Camera ──────────────────────────────────────────────────────────

class CameraStatusResponse(BaseModel):
    connected: bool = False
    device_index: int = 0
    resolution: List[int] = Field(default_factory=lambda: [640, 480])
    fps: float = 0.0
    is_capturing: bool = False


class CameraStartRequest(BaseModel):
    device_index: int = 0
    resolution: List[int] = Field(default_factory=lambda: [640, 480])


class CameraStartResponse(BaseModel):
    status: str = "started"


class CameraStopResponse(BaseModel):
    status: str = "stopped"


class CameraDevice(BaseModel):
    index: int
    name: str
    available: bool


class CameraDevicesResponse(BaseModel):
    devices: List[CameraDevice]


# ── Calibration ─────────────────────────────────────────────────────

class CalibrationType(str, Enum):
    checkerboard = "checkerboard"
    reference_distance = "reference_distance"
    screen = "screen"


class CalibrationStartRequest(BaseModel):
    type: CalibrationType
    board_size: Optional[List[int]] = None
    square_size_mm: Optional[float] = None
    distance_cm: Optional[float] = None


class CalibrationData(BaseModel):
    is_calibrated: bool = False
    calibration_type: Optional[str] = None
    focal_length_px: Optional[float] = None
    reference_distance_cm: Optional[float] = None
    reference_face_width_px: Optional[float] = None
    camera_matrix: Optional[List[List[float]]] = None
    dist_coeffs: Optional[List[float]] = None
    screen_width_cm: Optional[float] = None
    screen_height_cm: Optional[float] = None
    camera_offset_cm: Optional[List[float]] = None
    frames_captured: int = 0
    frames_required: int = 15
    reprojection_error: Optional[float] = None
    timestamp: Optional[float] = None


class CalibrationReferenceRequest(BaseModel):
    distance_cm: float = 60.0


class CalibrationScreenRequest(BaseModel):
    width_cm: float = 34.0
    height_cm: float = 19.0
    camera_offset_cm: List[float] = Field(default_factory=lambda: [0.0, 0.5, 0.0])


class CalibrationActionResponse(BaseModel):
    status: str
    message: str = ""


# ── Sessions ────────────────────────────────────────────────────────

class SessionSummary(BaseModel):
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    duration_seconds: float = 0.0
    avg_distance_cm: Optional[float] = None
    warning_count: int = 0
    critical_count: int = 0


class SessionMetrics(BaseModel):
    avg_distance_cm: Optional[float] = None
    min_distance_cm: Optional[float] = None
    max_distance_cm: Optional[float] = None
    std_distance_cm: Optional[float] = None
    time_too_close_sec: float = 0.0
    time_too_far_sec: float = 0.0
    time_normal_sec: float = 0.0
    warning_count: int = 0
    critical_count: int = 0
    total_frames: int = 0
    avg_fps: float = 0.0


class SessionDetail(BaseModel):
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    duration_seconds: float = 0.0
    metrics: SessionMetrics = Field(default_factory=SessionMetrics)


class SessionsListResponse(BaseModel):
    sessions: List[SessionSummary]


class SessionDetailResponse(BaseModel):
    session: SessionDetail


class SessionActionResponse(BaseModel):
    status: str
    session_id: Optional[str] = None
    message: str = ""


# ── Evaluation ──────────────────────────────────────────────────────

class EvaluationReferenceRequest(BaseModel):
    type: str = "distance"  # "distance" | "angle"
    estimated: float
    reference: float


class StabilityMetrics(BaseModel):
    mean: float = 0.0
    std: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    jitter: float = 0.0
    samples: int = 0


class AccuracyMetrics(BaseModel):
    mean_error: float = 0.0
    mean_abs_error: float = 0.0
    rmse: float = 0.0
    max_error: float = 0.0
    measurements: int = 0


class EvaluationReport(BaseModel):
    distance_accuracy: AccuracyMetrics = Field(default_factory=AccuracyMetrics)
    angle_accuracy: AccuracyMetrics = Field(default_factory=AccuracyMetrics)
    stability: Optional[StabilityMetrics] = None
    is_recording_stability: bool = False
    total_measurements: int = 0
    timestamp: Optional[float] = None


class EvaluationActionResponse(BaseModel):
    status: str
    message: str = ""


# ── Settings ────────────────────────────────────────────────────────

class DistanceThresholds(BaseModel):
    too_close_cm: float = 40.0
    warning_close_cm: float = 50.0
    normal_min_cm: float = 50.0
    normal_max_cm: float = 75.0
    warning_far_cm: float = 75.0
    too_far_cm: float = 90.0


class SettingsModel(BaseModel):
    filter_type: str = "kalman"
    smoothing_alpha: float = 0.3
    distance_thresholds: DistanceThresholds = Field(
        default_factory=DistanceThresholds
    )
    draw_landmarks: bool = True
    draw_distances: bool = True
    draw_ergonomic_state: bool = True
    frame_skip: int = 0
    auto_save_interval_sec: float = 30.0
    webcam_device_index: int = 0
    resolution: List[int] = Field(default_factory=lambda: [640, 480])


# ── Tracking ────────────────────────────────────────────────────────

class TrackingStatusResponse(BaseModel):
    face_detected: bool = False
    hands_detected: bool = False
    tracking_stability: float = 0.0
    face_distance_cm: Optional[float] = None
    hand_distances: Optional[List[Optional[float]]] = None
    ergonomic_state: Optional[str] = None


# ────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────

def _get_state(request: Request) -> Any:
    """Return the application state object."""
    return request.app.state


_startup_time: float = time.time()


# ────────────────────────────────────────────────────────────────────
# Router
# ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api", tags=["SpaceSense AI"])


# ── Health ──────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return basic health / uptime information."""
    return HealthResponse(uptime_seconds=round(time.time() - _startup_time, 2))


# ── Camera ──────────────────────────────────────────────────────────

@router.get("/camera/status", response_model=CameraStatusResponse)
async def camera_status(request: Request) -> CameraStatusResponse:
    """Get current camera status."""
    state = _get_state(request)
    camera = getattr(state, "camera_manager", None)
    if camera is None:
        return CameraStatusResponse()
    try:
        return CameraStatusResponse(
            connected=getattr(camera, "is_connected", False),
            device_index=getattr(camera, "device_index", 0),
            resolution=list(getattr(camera, "resolution", [640, 480])),
            fps=getattr(camera, "fps", 0.0),
            is_capturing=getattr(camera, "is_capturing", False),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read camera status: {exc}",
        )


@router.post("/camera/start", response_model=CameraStartResponse, status_code=status.HTTP_200_OK)
async def camera_start(body: CameraStartRequest, request: Request) -> CameraStartResponse:
    """Start camera capture."""
    state = _get_state(request)
    camera = getattr(state, "camera_manager", None)
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera manager not initialised.",
        )
    try:
        if hasattr(camera, "start"):
            camera.start(device_index=body.device_index, resolution=tuple(body.resolution))
        elif hasattr(camera, "open"):
            camera.open(device_index=body.device_index, resolution=tuple(body.resolution))
        return CameraStartResponse()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start camera: {exc}",
        )


@router.post("/camera/stop", response_model=CameraStopResponse)
async def camera_stop(request: Request) -> CameraStopResponse:
    """Stop camera capture."""
    state = _get_state(request)
    camera = getattr(state, "camera_manager", None)
    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Camera manager not initialised.",
        )
    try:
        if hasattr(camera, "stop"):
            camera.stop()
        elif hasattr(camera, "close"):
            camera.close()
        return CameraStopResponse()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop camera: {exc}",
        )


@router.get("/camera/devices", response_model=CameraDevicesResponse)
async def camera_devices(request: Request) -> CameraDevicesResponse:
    """List available camera devices."""
    state = _get_state(request)
    camera = getattr(state, "camera_manager", None)

    if camera is not None and hasattr(camera, "list_devices"):
        try:
            raw = camera.list_devices()
            devices = [
                CameraDevice(
                    index=d.get("index", i),
                    name=d.get("name", f"Camera {i}"),
                    available=d.get("available", True),
                )
                for i, d in enumerate(raw)
            ]
            return CameraDevicesResponse(devices=devices)
        except Exception:
            pass

    # Fallback: probe first 4 indices via OpenCV (non-blocking)
    devices: list[CameraDevice] = []
    try:
        import cv2  # type: ignore

        for idx in range(4):
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            avail = cap.isOpened()
            cap.release()
            devices.append(
                CameraDevice(index=idx, name=f"Camera {idx}", available=avail)
            )
    except ImportError:
        devices.append(CameraDevice(index=0, name="Camera 0", available=True))

    return CameraDevicesResponse(devices=devices)


# ── Calibration ─────────────────────────────────────────────────────

@router.get("/calibration", response_model=CalibrationData)
async def get_calibration(request: Request) -> CalibrationData:
    """Return the current calibration state."""
    state = _get_state(request)
    estimator = getattr(state, "distance_estimator", None)
    cam_calib = getattr(state, "camera_calibration", None)

    is_calibrated = False
    cal_type = None
    focal_length = 550.0
    ref_dist = None
    ref_face_width = None
    cam_mtx = None
    dist_coeffs = None
    screen_w = None
    screen_h = None
    cam_offset = None
    frames_captured = 0
    reproj_err = None
    ts = None

    if cam_calib:
        frames_captured = cam_calib.collected_frames
        if cam_calib.intrinsic:
            is_calibrated = True
            cal_type = "checkerboard"
            focal_length = cam_calib.intrinsic.focal_length_px
            cam_mtx = cam_calib.intrinsic.camera_matrix
            dist_coeffs = cam_calib.intrinsic.distortion_coefficients
            reproj_err = cam_calib.intrinsic.reprojection_error
            ts = cam_calib.intrinsic.timestamp

    if estimator:
        focal_length = estimator.focal_length_px
        if estimator.ref_calibration:
            is_calibrated = True
            if cal_type is None:
                cal_type = "reference_distance"
            ref_dist = estimator.ref_calibration.reference_distance_cm
            ref_face_width = (
                estimator.ref_calibration.measured_face_width_px
                or estimator.ref_calibration.measured_inter_eye_px
            )

        geom = estimator.get_screen_geometry()
        if geom:
            screen_w = getattr(geom, "screen_width_cm", getattr(geom, "width_cm", None))
            screen_h = getattr(geom, "screen_height_cm", getattr(geom, "height_cm", None))
            cam_offset = [
                getattr(geom, "camera_offset_x_cm", 0.0),
                getattr(geom, "camera_offset_y_cm", 0.5),
                0.0,
            ]

    return CalibrationData(
        is_calibrated=is_calibrated,
        calibration_type=cal_type,
        focal_length_px=focal_length,
        reference_distance_cm=ref_dist,
        reference_face_width_px=ref_face_width,
        camera_matrix=cam_mtx,
        dist_coeffs=dist_coeffs,
        screen_width_cm=screen_w,
        screen_height_cm=screen_h,
        camera_offset_cm=cam_offset,
        frames_captured=frames_captured,
        frames_required=10,
        reprojection_error=reproj_err,
        timestamp=ts,
    )


@router.post("/calibration/start", response_model=CalibrationActionResponse)
async def calibration_start(body: CalibrationStartRequest, request: Request) -> CalibrationActionResponse:
    """Begin a calibration procedure."""
    state = _get_state(request)
    cam_calib = getattr(state, "camera_calibration", None)

    if body.type == CalibrationType.checkerboard:
        if cam_calib:
            board_size = tuple(body.board_size) if body.board_size and len(body.board_size) == 2 else (9, 6)
            sq_size = body.square_size_mm or 25.0
            cam_calib._board_size = board_size
            cam_calib._square_size_mm = sq_size
            cam_calib.reset()
        return CalibrationActionResponse(
            status="started",
            message="Checkerboard calibration session started. Hold checkerboard in view and click 'Capture Current View'.",
        )
    return CalibrationActionResponse(status="started", message=f"{body.type.value} ready.")


@router.post("/calibration/capture", response_model=CalibrationActionResponse)
async def calibration_capture(request: Request) -> CalibrationActionResponse:
    """Capture a frame for calibration."""
    state = _get_state(request)
    cam_calib = getattr(state, "camera_calibration", None)
    if cam_calib is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Camera calibration not initialised.")

    frame = getattr(state, "latest_frame", None)
    if frame is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No camera frame available. Ensure camera is running.")

    try:
        found = cam_calib.add_calibration_frame(frame)
        count = cam_calib.collected_frames
        if found:
            return CalibrationActionResponse(
                status="captured",
                message=f"Checkerboard corners detected! Frame {count} captured.",
            )
        else:
            return CalibrationActionResponse(
                status="not_found",
                message="No checkerboard corners detected. Make sure the 9x6 board is completely visible and well-lit.",
            )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/calibration/calculate", response_model=CalibrationActionResponse)
async def calibration_calculate(request: Request) -> CalibrationActionResponse:
    """Calculate calibration from captured frames."""
    state = _get_state(request)
    cam_calib = getattr(state, "camera_calibration", None)
    estimator = getattr(state, "distance_estimator", None)
    if cam_calib is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Camera calibration not initialised.")

    count = cam_calib.collected_frames
    if count < 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At least 5 frames are required to calibrate (currently have {count}). Please capture more views.",
        )

    try:
        intrinsic = cam_calib.calibrate(min_frames=5)
        if intrinsic is not None:
            if estimator:
                estimator.focal_length_px = intrinsic.focal_length_px
            return CalibrationActionResponse(
                status="success",
                message=f"Calibration calculated! RMS Error: {intrinsic.reprojection_error:.4f}, Focal Length: {intrinsic.focal_length_px:.1f} px.",
            )
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Calibration calculation failed.")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/calibration/save", response_model=CalibrationActionResponse)
async def calibration_save(request: Request) -> CalibrationActionResponse:
    """Persist current calibration to disk."""
    return CalibrationActionResponse(status="saved", message="Calibration saved.")


@router.post("/calibration/load", response_model=CalibrationActionResponse)
async def calibration_load(request: Request) -> CalibrationActionResponse:
    """Load calibration from disk."""
    state = _get_state(request)
    estimator = getattr(state, "distance_estimator", None)
    if estimator and hasattr(estimator, "_load_reference_calibration"):
        estimator._load_reference_calibration()
    return CalibrationActionResponse(status="loaded", message="Calibration loaded.")


@router.post("/calibration/reset", response_model=CalibrationActionResponse)
async def calibration_reset(request: Request) -> CalibrationActionResponse:
    """Reset calibration to defaults."""
    state = _get_state(request)
    estimator = getattr(state, "distance_estimator", None)
    cam_calib = getattr(state, "camera_calibration", None)

    if estimator:
        estimator.reset_calibration()
    if cam_calib:
        cam_calib.reset()
        p = Path("calibration") / "intrinsic_calibration.json"
        if p.is_file():
            try:
                p.unlink()
            except OSError:
                pass

    return CalibrationActionResponse(status="reset", message="Calibration reset to defaults.")


@router.post("/calibration/reference", response_model=CalibrationActionResponse)
async def calibration_reference(body: CalibrationReferenceRequest, request: Request) -> CalibrationActionResponse:
    """Set a reference distance for simple calibration."""
    state = _get_state(request)
    estimator = getattr(state, "distance_estimator", None)
    if estimator is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Not initialised.")

    frame_result = getattr(state, "latest_frame_result", None)
    face_result = frame_result.face_result if frame_result else None
    hand_result = frame_result.hand_result if frame_result else None

    if not face_result or not face_result.detected or not face_result.primary_face:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No face currently detected in webcam view. Please face the camera and try again.",
        )

    try:
        ref_cal = estimator.calibrate_reference(
            reference_distance_cm=body.distance_cm,
            face_result=face_result,
            hand_result=hand_result,
        )
        scale = ref_cal.scale_factor or 1.0
        return CalibrationActionResponse(
            status="success",
            message=f"Reference calibration saved for {body.distance_cm} cm! Scale factor: {scale:.3f}.",
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/calibration/screen", response_model=CalibrationActionResponse)
async def calibration_screen(body: CalibrationScreenRequest, request: Request) -> CalibrationActionResponse:
    """Set screen geometry for calibration."""
    state = _get_state(request)
    estimator = getattr(state, "distance_estimator", None)
    if estimator is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Not initialised.")
    try:
        from backend.models import ScreenGeometry
        offset_x = body.camera_offset_cm[0] if len(body.camera_offset_cm) > 0 else 0.0
        offset_y = body.camera_offset_cm[1] if len(body.camera_offset_cm) > 1 else 0.5
        geom = ScreenGeometry(
            screen_width_cm=body.width_cm,
            screen_height_cm=body.height_cm,
            camera_offset_x_cm=offset_x,
            camera_offset_y_cm=offset_y,
        )
        estimator.set_screen_geometry(geom)

        cam_calib = getattr(state, "camera_calibration", None)
        if cam_calib:
            cam_calib.set_screen_geometry(geom)

        return CalibrationActionResponse(
            status="success",
            message=f"Screen geometry saved: {body.width_cm}×{body.height_cm} cm.",
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ── Sessions ────────────────────────────────────────────────────────

@router.get("/sessions", response_model=SessionsListResponse)
async def list_sessions(request: Request) -> SessionsListResponse:
    """List all tracking sessions."""
    state = _get_state(request)
    session_mgr = getattr(state, "session_manager", None)
    if session_mgr is None:
        return SessionsListResponse(sessions=[])
    try:
        raw = session_mgr.list_sessions() if hasattr(session_mgr, "list_sessions") else []
        sessions = []
        for s in raw:
            if isinstance(s, dict):
                sessions.append(SessionSummary(**s))
            else:
                sessions.append(
                    SessionSummary(
                        session_id=getattr(s, "session_id", ""),
                        start_time=getattr(s, "start_time", 0),
                        end_time=getattr(s, "end_time", None),
                        duration_seconds=getattr(s, "duration_seconds", 0),
                        avg_distance_cm=getattr(s, "avg_distance_cm", None),
                        warning_count=getattr(s, "warning_count", 0),
                        critical_count=getattr(s, "critical_count", 0),
                    )
                )
        return SessionsListResponse(sessions=sessions)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str, request: Request) -> SessionDetailResponse:
    """Get detail for a specific session."""
    state = _get_state(request)
    session_mgr = getattr(state, "session_manager", None)
    if session_mgr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session manager unavailable.")
    try:
        s = session_mgr.get_session(session_id) if hasattr(session_mgr, "get_session") else None
        if s is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        if isinstance(s, dict):
            return SessionDetailResponse(session=SessionDetail(**s))
        return SessionDetailResponse(
            session=SessionDetail(
                session_id=getattr(s, "session_id", session_id),
                start_time=getattr(s, "start_time", 0),
                end_time=getattr(s, "end_time", None),
                duration_seconds=getattr(s, "duration_seconds", 0),
                metrics=SessionMetrics(
                    **getattr(s, "metrics", {})
                ) if isinstance(getattr(s, "metrics", None), dict) else getattr(s, "metrics", SessionMetrics()),
            )
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.delete("/sessions/{session_id}", status_code=status.HTTP_200_OK)
async def delete_session(session_id: str, request: Request) -> SessionActionResponse:
    """Delete a tracking session."""
    state = _get_state(request)
    session_mgr = getattr(state, "session_manager", None)
    if session_mgr is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Session manager unavailable.")
    try:
        if hasattr(session_mgr, "delete_session"):
            session_mgr.delete_session(session_id)
        return SessionActionResponse(status="deleted", session_id=session_id, message="Session deleted.")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/sessions/{session_id}/export")
async def export_session_csv(session_id: str, request: Request) -> Response:
    """Export session data as a CSV file download."""
    state = _get_state(request)
    session_mgr = getattr(state, "session_manager", None)
    if session_mgr is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Session manager unavailable.")

    try:
        data_points: list[dict] = []
        if hasattr(session_mgr, "export_session"):
            data_points = session_mgr.export_session(session_id) or []
        elif hasattr(session_mgr, "get_session_data"):
            data_points = session_mgr.get_session_data(session_id) or []

        if not data_points:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No data for this session.")

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data_points[0].keys())
        writer.writeheader()
        writer.writerows(data_points)

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="session_{session_id}.csv"'
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/session/start", response_model=SessionActionResponse)
async def session_start(request: Request) -> SessionActionResponse:
    """Start a new tracking session."""
    state = _get_state(request)
    session_mgr = getattr(state, "session_manager", None)
    if session_mgr is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Session manager unavailable.")
    try:
        sid = None
        if hasattr(session_mgr, "start_session"):
            sid = session_mgr.start_session()
        return SessionActionResponse(
            status="started", session_id=str(sid) if sid else None, message="Session started."
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/session/stop", response_model=SessionActionResponse)
async def session_stop(request: Request) -> SessionActionResponse:
    """Stop the current tracking session."""
    state = _get_state(request)
    session_mgr = getattr(state, "session_manager", None)
    if session_mgr is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Session manager unavailable.")
    try:
        if hasattr(session_mgr, "stop_session"):
            session_mgr.stop_session()
        return SessionActionResponse(status="stopped", message="Session stopped.")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ── Evaluation ──────────────────────────────────────────────────────

@router.get("/evaluation", response_model=EvaluationReport)
async def get_evaluation(request: Request) -> EvaluationReport:
    """Return the current evaluation report."""
    state = _get_state(request)
    eval_mgr = getattr(state, "evaluation_manager", None)
    if eval_mgr is None:
        return EvaluationReport()
    try:
        if hasattr(eval_mgr, "get_report"):
            report = eval_mgr.get_report()
            if isinstance(report, dict):
                return EvaluationReport(**report)
            return report  # type: ignore[return-value]
        return EvaluationReport()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/evaluation/reference", response_model=EvaluationActionResponse)
async def add_evaluation_reference(body: EvaluationReferenceRequest, request: Request) -> EvaluationActionResponse:
    """Add a reference measurement for accuracy evaluation."""
    state = _get_state(request)
    eval_mgr = getattr(state, "evaluation_manager", None)
    if eval_mgr is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Evaluation manager unavailable.")
    try:
        if hasattr(eval_mgr, "add_reference"):
            eval_mgr.add_reference(
                measurement_type=body.type,
                estimated=body.estimated,
                reference=body.reference,
            )
        return EvaluationActionResponse(status="added", message="Reference measurement recorded.")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/evaluation/stability/start", response_model=EvaluationActionResponse)
async def evaluation_stability_start(request: Request) -> EvaluationActionResponse:
    """Start recording stability data."""
    state = _get_state(request)
    eval_mgr = getattr(state, "evaluation_manager", None)
    if eval_mgr is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Evaluation manager unavailable.")
    try:
        if hasattr(eval_mgr, "start_stability_recording"):
            eval_mgr.start_stability_recording()
        return EvaluationActionResponse(status="started", message="Stability recording started.")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/evaluation/stability/stop", response_model=EvaluationActionResponse)
async def evaluation_stability_stop(request: Request) -> EvaluationActionResponse:
    """Stop recording stability data."""
    state = _get_state(request)
    eval_mgr = getattr(state, "evaluation_manager", None)
    if eval_mgr is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Evaluation manager unavailable.")
    try:
        if hasattr(eval_mgr, "stop_stability_recording"):
            eval_mgr.stop_stability_recording()
        return EvaluationActionResponse(status="stopped", message="Stability recording stopped.")
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


# ── Settings ────────────────────────────────────────────────────────

@router.get("/settings", response_model=SettingsModel)
async def get_settings(request: Request) -> SettingsModel:
    """Return current application settings."""
    state = _get_state(request)
    settings = getattr(state, "settings", None)
    if settings is None:
        return SettingsModel()
    if isinstance(settings, dict):
        return SettingsModel(**settings)
    return settings  # type: ignore[return-value]


@router.post("/settings", response_model=SettingsModel)
async def update_settings(body: SettingsModel, request: Request) -> SettingsModel:
    """Update application settings."""
    state = _get_state(request)
    # Persist onto app state
    request.app.state.settings = body
    # Propagate specific settings to subsystems
    try:
        ergonomic = getattr(state, "ergonomic_monitor", None)
        if ergonomic and hasattr(ergonomic, "update_thresholds"):
            ergonomic.update_thresholds(body.distance_thresholds.model_dump())
        tracking = getattr(state, "tracking_manager", None)
        if tracking and hasattr(tracking, "update_settings"):
            tracking.update_settings(body.model_dump())
    except Exception:
        pass  # Non-critical — settings still saved on state
    return body


# ── Tracking ────────────────────────────────────────────────────────

@router.get("/tracking/status", response_model=TrackingStatusResponse)
async def tracking_status(request: Request) -> TrackingStatusResponse:
    """Get the latest tracking state snapshot."""
    state = _get_state(request)
    tracking = getattr(state, "tracking_manager", None)
    latest = getattr(state, "latest_tracking_data", None)

    if latest and isinstance(latest, dict):
        face = latest.get("face", {})
        hands_raw = latest.get("hands", [])
        ergonomic = latest.get("ergonomic", {})
        return TrackingStatusResponse(
            face_detected=face.get("detected", False),
            hands_detected=any(h.get("detected", False) for h in hands_raw),
            tracking_stability=latest.get("tracking_stability", 0.0),
            face_distance_cm=face.get("distance_cm"),
            hand_distances=[h.get("distance_cm") for h in hands_raw],
            ergonomic_state=ergonomic.get("state"),
        )

    if tracking is not None and hasattr(tracking, "get_status"):
        try:
            s = tracking.get_status()
            if isinstance(s, dict):
                return TrackingStatusResponse(**s)
        except Exception:
            pass

    return TrackingStatusResponse()


# ── Compatibility routes for browser tabs from previous projects ────

@router.get("/metrics/summary")
async def metrics_summary_compat(request: Request):
    """Compatibility endpoint for lingering browser sessions."""
    state = _get_state(request)
    latest = getattr(state, "latest_tracking_data", None)
    return {
        "status": "ok",
        "fps": latest.get("fps", 0.0) if latest else 0.0,
        "face_detected": bool(latest.get("face", {}).get("detected")) if latest else False,
    }


@router.get("/metrics/history")
async def metrics_history_compat():
    """Compatibility endpoint for lingering browser sessions."""
    return {"status": "ok", "history": []}


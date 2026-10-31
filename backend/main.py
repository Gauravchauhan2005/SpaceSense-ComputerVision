"""
SpaceSense AI — Main Application Entry Point

FastAPI application that orchestrates camera capture, the computer-vision
pipeline, real-time WebSocket streaming, and REST API endpoints.

Run with:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.camera.camera_manager import CameraManager
from backend.vision.frame_processor import FrameProcessor
from backend.geometry.distance_estimator import DistanceEstimator
from backend.geometry.camera_calibration import CameraCalibration
from backend.geometry.angle_calculator import AngleCalculator
from backend.analysis.motion_analyzer import MotionAnalyzer
from backend.analysis.ergonomic_monitor import ErgonomicMonitor
from backend.tracking.tracking_manager import TrackingManager
from backend.analysis.evaluation import EvaluationManager
from backend.database.database_manager import DatabaseManager
from backend.database.session_manager import SessionManager

from backend.api.routes import SettingsModel, router as api_router
from backend.api.websocket import manager as ws_manager, tracking_websocket_endpoint

# ── Logging ─────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("spacesense.main")

# ────────────────────────────────────────────────────────────────────
# Lifecycle — startup / shutdown
# ────────────────────────────────────────────────────────────────────

_processing_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise subsystems on startup and tear them down on shutdown."""
    global _processing_task

    logger.info("SpaceSense AI — starting up …")

    app.state.startup_time = time.time()
    app.state.settings = SettingsModel()

    # ── Camera ──
    try:
        app.state.camera_manager = CameraManager(auto_start=True)
        logger.info("CameraManager initialised and started.")
    except Exception as exc:
        logger.warning("CameraManager init failed: %s", exc)
        app.state.camera_manager = None

    # ── Frame Processor ──
    try:
        app.state.frame_processor = FrameProcessor(mirror=True)
        logger.info("FrameProcessor initialised.")
    except Exception as exc:
        logger.warning("FrameProcessor init failed: %s", exc)
        app.state.frame_processor = None

    # ── Distance Estimator ──
    try:
        app.state.distance_estimator = DistanceEstimator()
        logger.info("DistanceEstimator initialised.")
    except Exception as exc:
        logger.warning("DistanceEstimator init failed: %s", exc)
        app.state.distance_estimator = None

    # ── Camera Calibration ──
    try:
        app.state.camera_calibration = CameraCalibration()
        logger.info("CameraCalibration initialised.")
        if app.state.camera_calibration.intrinsic and app.state.distance_estimator:
            app.state.distance_estimator.focal_length_px = app.state.camera_calibration.intrinsic.focal_length_px
    except Exception as exc:
        logger.warning("CameraCalibration init failed: %s", exc)
        app.state.camera_calibration = None

    # ── Angle Calculator ──
    app.state.angle_calculator = AngleCalculator()

    # ── Motion Analyzers (one per hand) ──
    app.state.motion_analyzer_left = MotionAnalyzer()
    app.state.motion_analyzer_right = MotionAnalyzer()

    # ── Ergonomic Monitor ──
    app.state.ergonomic_monitor = ErgonomicMonitor()

    # ── Tracking Manager ──
    try:
        app.state.tracking_manager = TrackingManager()
    except Exception as exc:
        logger.warning("TrackingManager init failed: %s", exc)
        app.state.tracking_manager = None

    # ── Evaluation Manager ──
    app.state.evaluation_manager = EvaluationManager()

    # ── Database & Sessions ──
    try:
        db = DatabaseManager()
        await db.initialize()
        app.state.database_manager = db
        app.state.session_manager = SessionManager(db)
        logger.info("Database initialised.")
    except Exception as exc:
        logger.warning("Database init failed: %s", exc)
        app.state.database_manager = None
        app.state.session_manager = None

    app.state.latest_tracking_data: Optional[Dict[str, Any]] = None

    # ── Start background processing loop ──
    _processing_task = asyncio.create_task(_processing_loop(app))
    logger.info("Background processing loop started.")

    yield  # ─── application is running ───

    # ── Shutdown ──
    logger.info("SpaceSense AI — shutting down …")

    if _processing_task and not _processing_task.done():
        _processing_task.cancel()
        try:
            await _processing_task
        except asyncio.CancelledError:
            pass

    cam = getattr(app.state, "camera_manager", None)
    if cam is not None:
        cam.stop()

    fp = getattr(app.state, "frame_processor", None)
    if fp is not None:
        fp.close()

    db = getattr(app.state, "database_manager", None)
    if db is not None:
        await db.close()

    logger.info("Shutdown complete.")


# ────────────────────────────────────────────────────────────────────
# Background Processing Loop
# ────────────────────────────────────────────────────────────────────

async def _processing_loop(app: FastAPI) -> None:
    """
    Continuous loop that:
      1. Grabs a frame from the camera (in a thread)
      2. Runs CV pipeline (face + hand detection)
      3. Computes distances, angles, motion, ergonomic state
      4. Broadcasts results via WebSocket
      5. Periodically persists metrics to database
    """
    frame_number: int = 0
    last_db_save: float = time.time()
    fps_window: list[float] = []

    while True:
        try:
            camera: Optional[CameraManager] = getattr(app.state, "camera_manager", None)
            processor: Optional[FrameProcessor] = getattr(app.state, "frame_processor", None)

            if camera is None or not camera.is_running:
                await asyncio.sleep(0.1)
                continue

            # 1. Capture frame (off event loop)
            t0 = time.time()
            frame = await asyncio.to_thread(camera.get_frame)
            if frame is None:
                await asyncio.sleep(0.01)
                continue

            frame_number += 1
            h_frame, w_frame = frame.shape[:2]
            app.state.latest_frame = frame

            # 2. Process through CV pipeline
            annotated_frame = frame.copy()
            if processor is not None and processor.mirror:
                annotated_frame = cv2.flip(annotated_frame, 1)

            frame_result = None

            if processor is not None:
                frame_result = await asyncio.to_thread(processor.process, frame)

            # 3. Extract results and compute metrics
            face_distance_cm: Optional[float] = None
            left_hand_distance_cm: Optional[float] = None
            right_hand_distance_cm: Optional[float] = None
            finger_angles: dict = {}
            hand_body_angle: dict = {}
            hand_orientation: dict = {}
            movement_data_left: dict = {}
            movement_data_right: dict = {}

            dist_est: Optional[DistanceEstimator] = getattr(app.state, "distance_estimator", None)
            angle_calc: AngleCalculator = app.state.angle_calculator
            ergo: ErgonomicMonitor = app.state.ergonomic_monitor

            face_payload: Dict[str, Any] = {"detected": False}
            hands_payload: list[Dict[str, Any]] = []

            if frame_result is not None:
                face_result = frame_result.face_result
                hand_result = frame_result.hand_result

                # Draw landmarks on annotated frame
                if face_result.detected:
                    processor._face_tracker.draw_landmarks(annotated_frame, face_result, color=(0, 255, 180), radius=1)
                    processor._face_tracker.draw_bounding_boxes(annotated_frame, face_result, color=(83, 183, 255))

                if hand_result.detected:
                    processor._hand_tracker.draw_skeleton(annotated_frame, hand_result, color=(255, 183, 77))
                    processor._hand_tracker.draw_landmarks(annotated_frame, hand_result, color=(255, 92, 101), radius=4)

                    # Draw handedness labels on annotated frame
                    for hand in hand_result.hands:
                        if hand.landmarks:
                            wrist = hand.landmarks[0]
                            lbl = f"{hand.handedness.value} Hand ({int(hand.confidence * 100)}%)"
                            lbl_color = (83, 183, 255) if hand.handedness.value == "Right" else (255, 183, 77)
                            cv2.putText(
                                annotated_frame,
                                lbl,
                                (max(10, int(wrist.x) - 40), max(20, int(wrist.y) - 15)),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.5,
                                lbl_color,
                                2,
                            )

                # Distance estimation
                if dist_est is not None:
                    face_dist_result = dist_est.estimate_face_distance(face_result)
                    if face_dist_result is not None:
                        face_distance_cm = face_dist_result.distance_cm

                    if hand_result.left_hand is not None:
                        left_dist = dist_est.estimate_hand_distance(hand_result, which="left")
                        if left_dist is not None:
                            left_hand_distance_cm = left_dist.distance_cm

                    if hand_result.right_hand is not None:
                        right_dist = dist_est.estimate_hand_distance(hand_result, which="right")
                        if right_dist is not None:
                            right_hand_distance_cm = right_dist.distance_cm

                # Closest object
                closest_result = dist_est.find_closest_object(face_result, hand_result) if dist_est else None

                # Whole Hand vs Body Symmetry Axis Angle
                primary_hand = hand_result.right_hand or hand_result.left_hand or (hand_result.hands[0] if hand_result.hands else None)
                face_lms = face_result.primary_face.landmarks if (face_result.detected and face_result.primary_face) else None
                if primary_hand is not None and primary_hand.landmarks:
                    try:
                        hand_body_angle = angle_calc.calculate_hand_body_angle(
                            primary_hand.landmarks,
                            face_landmarks=face_lms,
                            frame_width=w_frame,
                            frame_height=h_frame,
                        )
                        hand_orientation = angle_calc.calculate_hand_orientation(primary_hand.landmarks)
                    except Exception as exc:
                        logger.warning("Error calculating hand_body_angle: %s", exc)
                        hand_body_angle = {}

                    # Draw Body Symmetry Line on annotated frame
                    if hand_body_angle and "symmetry_line" in hand_body_angle:
                        try:
                            sym_p1 = (int(hand_body_angle["symmetry_line"][0][0]), int(hand_body_angle["symmetry_line"][0][1]))
                            sym_p2 = (int(hand_body_angle["symmetry_line"][1][0]), int(hand_body_angle["symmetry_line"][1][1]))
                            cv2.line(annotated_frame, sym_p1, sym_p2, (255, 255, 0), 2, cv2.LINE_AA)
                            orig = hand_body_angle.get("symmetry_origin")
                            if orig:
                                ox, oy = int(orig[0]), int(orig[1])
                                cv2.circle(annotated_frame, (ox, oy), 4, (255, 255, 0), -1)
                                cv2.putText(
                                    annotated_frame,
                                    "Body Symmetry Line",
                                    (max(10, ox + 10), max(25, oy + 5)),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.45,
                                    (255, 255, 0),
                                    1,
                                    cv2.LINE_AA,
                                )
                        except Exception as exc:
                            logger.debug("Drawing symmetry line error: %s", exc)

                    # Draw Whole Hand Vector & Angle Badge
                    if hand_body_angle and "hand_vector" in hand_body_angle:
                        try:
                            w_pt = (int(hand_body_angle["hand_vector"][0][0]), int(hand_body_angle["hand_vector"][0][1]))
                            t_pt = (int(hand_body_angle["hand_vector"][1][0]), int(hand_body_angle["hand_vector"][1][1]))
                            cv2.line(annotated_frame, w_pt, t_pt, (55, 201, 139), 3, cv2.LINE_AA)
                            cv2.circle(annotated_frame, w_pt, 5, (83, 183, 255), -1)
                            cv2.circle(annotated_frame, t_pt, 5, (55, 201, 139), -1)

                            angle_val = hand_body_angle.get("angle_deg", 0.0)
                            mid_x = int((w_pt[0] + t_pt[0]) / 2)
                            mid_y = int((w_pt[1] + t_pt[1]) / 2)
                            badge_x = min(w_frame - 150, max(10, mid_x + 15))
                            badge_y = min(h_frame - 20, max(30, mid_y - 10))

                            cv2.rectangle(annotated_frame, (badge_x - 5, badge_y - 18), (badge_x + 135, badge_y + 8), (16, 19, 24), -1)
                            cv2.rectangle(annotated_frame, (badge_x - 5, badge_y - 18), (badge_x + 135, badge_y + 8), (55, 201, 139), 1)
                            cv2.putText(
                                annotated_frame,
                                f"Angle: {angle_val:.1f} deg",
                                (badge_x, badge_y - 2),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.45,
                                (255, 255, 255),
                                1,
                                cv2.LINE_AA,
                            )
                        except Exception as exc:
                            logger.debug("Drawing hand vector error: %s", exc)

                # Motion analysis
                now = time.time()
                if hand_result.left_hand and hand_result.left_hand.hand_center:
                    lc = hand_result.left_hand.hand_center
                    ma_left: MotionAnalyzer = app.state.motion_analyzer_left
                    motion_res = ma_left.update(lc.x, lc.y, now)
                    movement_data_left = {
                        "speed_px_per_sec": round(motion_res.velocity, 1),
                        "direction_deg": round(motion_res.direction_deg, 1),
                        "cumulative_distance": round(motion_res.cumulative_distance, 1),
                    }

                if hand_result.right_hand and hand_result.right_hand.hand_center:
                    rc = hand_result.right_hand.hand_center
                    ma_right: MotionAnalyzer = app.state.motion_analyzer_right
                    motion_res = ma_right.update(rc.x, rc.y, now)
                    movement_data_right = {
                        "speed_px_per_sec": round(motion_res.velocity, 1),
                        "direction_deg": round(motion_res.direction_deg, 1),
                        "cumulative_distance": round(motion_res.cumulative_distance, 1),
                    }

                # Build face payload
                if face_result.detected and face_result.primary_face:
                    pf = face_result.primary_face
                    face_payload = {
                        "detected": True,
                        "distance_cm": face_distance_cm,
                        "confidence": round(pf.confidence, 2),
                        "center": [pf.center.x, pf.center.y] if pf.center else None,
                        "bbox": [pf.bounding_box.x_min, pf.bounding_box.y_min,
                                 pf.bounding_box.x_max, pf.bounding_box.y_max] if pf.bounding_box else None,
                        "landmarks_count": len(pf.landmarks.all_landmarks),
                        "inter_eye_px": round(pf.inter_eye_distance_px, 1) if pf.inter_eye_distance_px else None,
                    }

                # Build hands payload
                for hand in hand_result.hands:
                    h_dist = left_hand_distance_cm if hand.handedness.value == "Left" else right_hand_distance_cm
                    h_movement = movement_data_left if hand.handedness.value == "Left" else movement_data_right
                    h_angles = finger_angles if hand == primary_hand else {}
                    h_orient = hand_orientation if hand == primary_hand else {}

                    # Calculate per-hand body angle
                    h_body_angle = None
                    if hand.landmarks:
                        try:
                            h_body_angle = angle_calc.calculate_hand_body_angle(
                                hand.landmarks,
                                face_landmarks=face_lms,
                                frame_width=w_frame,
                                frame_height=h_frame,
                            )
                        except Exception:
                            h_body_angle = None

                    hands_payload.append({
                        "label": hand.handedness.value,
                        "detected": True,
                        "distance_cm": h_dist,
                        "center": [round(hand.hand_center.x, 1), round(hand.hand_center.y, 1)] if hand.hand_center else None,
                        "center_normalized": [
                            round(hand.hand_center.x / w_frame, 4),
                            round(hand.hand_center.y / h_frame, 4),
                        ] if (hand.hand_center and w_frame > 0 and h_frame > 0) else None,
                        "wrist": [round(hand.landmarks[0].x, 1), round(hand.landmarks[0].y, 1)] if hand.landmarks else None,
                        "palm_width_px": round(hand.palm_width_px, 1) if hand.palm_width_px else None,
                        "finger_angles": h_angles,
                        "hand_body_angle": h_body_angle if (h_body_angle and "angle_deg" in h_body_angle) else (hand_body_angle if (hand_body_angle and "angle_deg" in hand_body_angle) else None),
                        "orientation_deg": h_orient.get("rotation_deg"),
                        "orientation_direction": h_orient.get("direction"),
                        "movement": h_movement if h_movement else None,
                        "confidence": round(hand.confidence, 2),
                    })

            # Ergonomic state
            now = time.time()
            ergo_state = ergo.update(face_distance_cm, now)
            ergo_status = ergo.get_status(now)

            ergonomic_payload = {
                "state": ergo_state.value,
                "face_distance_cm": round(face_distance_cm, 1) if face_distance_cm else None,
                "smoothed_distance_cm": round(ergo.smoothed_distance, 1) if ergo.smoothed_distance else None,
                "time_in_state_sec": round(ergo_status.time_in_state, 1),
                "warning_count": ergo_status.warning_count,
                "critical_count": ergo_status.critical_count,
            }

            # FPS
            t1 = time.time()
            fps_window.append(t1)
            if len(fps_window) > 60:
                fps_window = fps_window[-60:]
            current_fps = 0.0
            if len(fps_window) >= 2:
                elapsed = fps_window[-1] - fps_window[0]
                current_fps = (len(fps_window) - 1) / elapsed if elapsed > 0 else 0.0

            processing_time_ms = (t1 - t0) * 1000.0

            # Closest object
            closest_payload = None
            if closest_result and closest_result.label:
                closest_payload = {
                    "name": closest_result.label,
                    "distance_cm": closest_result.distance_cm,
                }

            # Update evaluation
            eval_mgr: EvaluationManager = app.state.evaluation_manager
            eval_mgr.record_frame(processing_time_ms, current_fps,
                                  face_detected=face_payload.get("detected", False),
                                  hands_detected=len(hands_payload) > 0)

            # Build tracking data payload
            tracking_data: Dict[str, Any] = {
                "type": "tracking_data",
                "timestamp": t1,
                "frame_number": frame_number,
                "fps": round(current_fps, 1),
                "processing_time_ms": round(processing_time_ms, 1),
                "camera_resolution": [w_frame, h_frame],
                "face": face_payload,
                "hands": hands_payload,
                "hand_body_angle": hand_body_angle if (hand_body_angle and "angle_deg" in hand_body_angle) else None,
                "closest_object": closest_payload,
                "ergonomic": ergonomic_payload,
            }

            app.state.latest_tracking_data = tracking_data
            app.state.latest_frame_result = frame_result
            app.state.latest_annotated_frame = annotated_frame

            # Broadcast via WebSocket
            if ws_manager.active_count > 0:
                await ws_manager.broadcast_tracking_data(tracking_data)

                # Send annotated frame
                try:
                    success, jpeg_buf = cv2.imencode(
                        ".jpg", annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 75]
                    )
                    if success:
                        h_frame, w_frame = annotated_frame.shape[:2]
                        await ws_manager.broadcast_frame(
                            jpeg_buf.tobytes(), w_frame, h_frame
                        )
                except Exception as exc:
                    logger.debug("Frame encoding error: %s", exc)

            # Periodic DB save
            settings = getattr(app.state, "settings", None)
            save_interval = settings.auto_save_interval_sec if settings else 30.0
            if time.time() - last_db_save >= save_interval:
                last_db_save = time.time()
                session_mgr = getattr(app.state, "session_manager", None)
                if session_mgr is not None:
                    try:
                        await session_mgr.save_metrics(tracking_data)
                    except Exception as exc:
                        logger.debug("DB save error: %s", exc)

            # Yield control
            if processing_time_ms < 10:
                await asyncio.sleep(0.005)

        except asyncio.CancelledError:
            logger.info("Processing loop cancelled.")
            break
        except Exception as exc:
            logger.error("Processing loop error: %s", exc, exc_info=True)
            await asyncio.sleep(0.5)


# ────────────────────────────────────────────────────────────────────
# Application Factory
# ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SpaceSense AI",
    description="Real-time computer-vision distance & ergonomic tracking API.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount REST routes ───────────────────────────────────────────────

app.include_router(api_router)

# ── Mount WebSocket ─────────────────────────────────────────────────

app.websocket("/ws/tracking")(tracking_websocket_endpoint)
app.websocket("/ws/live-stream")(tracking_websocket_endpoint)



# ────────────────────────────────────────────────────────────────────
# Convenience: ``python -m backend.main``
# ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

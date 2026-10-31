// ============================================================================
// SpaceSense AI — Frontend TypeScript Definitions
// ============================================================================

export type ErgonomicState = 'NORMAL' | 'WARNING' | 'CRITICAL';

export interface FaceData {
  detected: boolean;
  distance_cm?: number | null;
  confidence?: number;
  center?: [number, number] | null;
  bbox?: [number, number, number, number] | null;
  landmarks_count?: number;
  inter_eye_px?: number | null;
}

export interface HandMovement {
  speed_px_per_sec: number;
  direction_deg: number;
  cumulative_distance: number;
}

export interface HandBodyAngleData {
  angle_deg: number;
  acute_angle_deg: number;
  lateral_direction: 'left' | 'right' | 'aligned' | string;
  hand_vector: [[number, number], [number, number]];
  symmetry_line: [[number, number], [number, number]];
  symmetry_origin?: [number, number];
}

export interface SingleHandData {
  label: 'Left' | 'Right' | string;
  detected: boolean;
  distance_cm?: number | null;
  center?: [number, number] | null;
  center_normalized?: [number, number] | null;
  wrist?: [number, number] | null;
  palm_width_px?: number | null;
  finger_angles?: Record<string, Record<string, number>>;
  hand_body_angle?: HandBodyAngleData | null;
  orientation_deg?: number | null;
  orientation_direction?: string | null;
  movement?: HandMovement | null;
  confidence?: number;
}

export interface ClosestObject {
  name: string;
  distance_cm: number;
}

export interface ErgonomicData {
  state: ErgonomicState;
  face_distance_cm?: number | null;
  smoothed_distance_cm?: number | null;
  time_in_state_sec: number;
  warning_count: number;
  critical_count: number;
}

export interface TrackingData {
  type: 'tracking_data';
  timestamp: number;
  frame_number: number;
  fps: number;
  processing_time_ms: number;
  camera_resolution?: [number, number] | null;
  face: FaceData;
  hands: SingleHandData[];
  hand_body_angle?: HandBodyAngleData | null;
  closest_object: ClosestObject | null;
  ergonomic: ErgonomicData | null;
}

export interface FrameMessage {
  type: 'frame';
  data: string; // base64 JPEG
  width: number;
  height: number;
}

export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

// ---------------------------------------------------------------------------
// REST API Models
// ---------------------------------------------------------------------------

export interface CameraStatus {
  connected: boolean;
  device_index: number;
  resolution: [number, number];
  fps: number;
  is_capturing: boolean;
}

export interface CameraDevice {
  index: number;
  name: string;
  available: boolean;
}

export interface CalibrationData {
  is_calibrated: boolean;
  calibration_type?: string | null;
  focal_length_px?: number | null;
  reference_distance_cm?: number | null;
  reference_face_width_px?: number | null;
  camera_matrix?: number[][] | null;
  dist_coeffs?: number[] | null;
  screen_width_cm?: number | null;
  screen_height_cm?: number | null;
  camera_offset_cm?: number[] | null;
  frames_captured: number;
  frames_required: number;
  reprojection_error?: number | null;
  timestamp?: number | null;
}

export interface SessionSummary {
  session_id: string;
  start_time: number;
  end_time?: number | null;
  duration_seconds: number;
  avg_distance_cm?: number | null;
  warning_count: number;
  critical_count: number;
}

export interface SessionMetrics {
  avg_distance_cm?: number | null;
  min_distance_cm?: number | null;
  max_distance_cm?: number | null;
  std_distance_cm?: number | null;
  time_too_close_sec: number;
  time_too_far_sec: number;
  time_normal_sec: number;
  warning_count: number;
  critical_count: number;
  total_frames: number;
  avg_fps: number;
}

export interface SessionDetail {
  session_id: string;
  start_time: number;
  end_time?: number | null;
  duration_seconds: number;
  metrics: any[];
}

export interface EvaluationAccuracy {
  mean_abs_error: number;
  rmse: number;
  max_error: number;
  measurements: number;
}

export interface EvaluationReport {
  fps_mean?: number;
  fps_current?: number;
  latency_mean_ms?: number;
  latency_median_ms?: number;
  latency_p95_ms?: number;
  latency_p99_ms?: number;
  latency_min_ms?: number;
  latency_max_ms?: number;
  face_availability_pct?: number;
  hand_availability_pct?: number;
  total_frames?: number;
  distance_accuracy?: EvaluationAccuracy;
  angle_accuracy?: {
    mean_error: number;
    mean_abs_error: number;
    max_error: number;
    measurements: number;
  };
  stability?: {
    mean: number;
    std: number;
    jitter: number;
    samples: number;
  } | null;
  is_recording_stability?: boolean;
  total_measurements?: number;
  timestamp?: number;
}

export interface DistanceThresholds {
  too_close_cm: number;
  warning_close_cm: number;
  normal_min_cm: number;
  normal_max_cm: number;
  warning_far_cm: number;
  too_far_cm: number;
}

export interface AppSettings {
  filter_type: string;
  smoothing_alpha: number;
  distance_thresholds: DistanceThresholds;
  draw_landmarks: boolean;
  draw_distances: boolean;
  draw_ergonomic_state: boolean;
  frame_skip: number;
  auto_save_interval_sec: number;
  webcam_device_index: number;
  resolution: [number, number];
}

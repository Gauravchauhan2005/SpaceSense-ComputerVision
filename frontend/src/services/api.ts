// ============================================================================
// SpaceSense AI — REST API Client
// ============================================================================

import type {
  CameraStatus,
  CameraDevice,
  CalibrationData,
  SessionSummary,
  SessionDetail,
  EvaluationReport,
  AppSettings,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE !== undefined && import.meta.env.VITE_API_BASE !== ''
  ? import.meta.env.VITE_API_BASE
  : (window.location.port === '5173' ? '' : `${window.location.protocol}//${window.location.hostname}:8000`);

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errorMsg = `HTTP ${res.status} ${res.statusText}`;
    try {
      const err = await res.json();
      if (err.detail) errorMsg = err.detail;
    } catch {
      // ignore
    }
    throw new Error(errorMsg);
  }

  return res.json();
}

export const api = {
  // Health
  getHealth: () => request<{ status: string; version: string; uptime_seconds: number }>('/api/health'),

  // Camera
  getCameraStatus: () => request<CameraStatus>('/api/camera/status'),
  startCamera: (device_index = 0, resolution = [640, 480]) =>
    request<{ status: string }>('/api/camera/start', {
      method: 'POST',
      body: JSON.stringify({ device_index, resolution }),
    }),
  stopCamera: () => request<{ status: string }>('/api/camera/stop', { method: 'POST' }),
  getCameraDevices: () => request<{ devices: CameraDevice[] }>('/api/camera/devices'),

  // Calibration
  getCalibration: () => request<CalibrationData>('/api/calibration'),
  startCalibration: (params: { type: string; board_size?: number[]; square_size_mm?: number; distance_cm?: number }) =>
    request<{ status: string; message: string }>('/api/calibration/start', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
  captureCalibrationFrame: () =>
    request<{ status: string; message: string }>('/api/calibration/capture', { method: 'POST' }),
  calculateCalibration: () =>
    request<{ status: string; message: string }>('/api/calibration/calculate', { method: 'POST' }),
  saveCalibration: () =>
    request<{ status: string; message: string }>('/api/calibration/save', { method: 'POST' }),
  resetCalibration: () =>
    request<{ status: string; message: string }>('/api/calibration/reset', { method: 'POST' }),
  setReferenceDistance: (distance_cm: number) =>
    request<{ status: string; message: string }>('/api/calibration/reference', {
      method: 'POST',
      body: JSON.stringify({ distance_cm }),
    }),
  setScreenGeometry: (width_cm: number, height_cm: number, camera_offset_cm = [0, 0.5, 0]) =>
    request<{ status: string; message: string }>('/api/calibration/screen', {
      method: 'POST',
      body: JSON.stringify({ width_cm, height_cm, camera_offset_cm }),
    }),

  // Sessions
  getSessions: () => request<{ sessions: SessionSummary[] }>('/api/sessions'),
  getSession: (id: string) => request<{ session: SessionDetail }>(`/api/sessions/${id}`),
  deleteSession: (id: string) => request<{ status: string }>(`/api/sessions/${id}`, { method: 'DELETE' }),
  startSession: () => request<{ status: string; session_id?: string }>('/api/session/start', { method: 'POST' }),
  stopSession: () => request<{ status: string }>('/api/session/stop', { method: 'POST' }),
  exportSessionUrl: (id: string) => `${API_BASE}/api/sessions/${id}/export`,

  // Evaluation
  getEvaluation: () => request<EvaluationReport>('/api/evaluation'),
  addEvaluationReference: (type: 'distance' | 'angle', estimated: number, reference: number) =>
    request<{ status: string; message: string }>('/api/evaluation/reference', {
      method: 'POST',
      body: JSON.stringify({ type, estimated, reference }),
    }),
  startStabilityRecording: () =>
    request<{ status: string; message: string }>('/api/evaluation/stability/start', { method: 'POST' }),
  stopStabilityRecording: () =>
    request<{ status: string; message: string }>('/api/evaluation/stability/stop', { method: 'POST' }),

  // Settings
  getSettings: () => request<AppSettings>('/api/settings'),
  updateSettings: (settings: AppSettings) =>
    request<AppSettings>('/api/settings', {
      method: 'POST',
      body: JSON.stringify(settings),
    }),
};

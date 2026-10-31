import React, { useState, useEffect } from 'react';
import { Crosshair, Camera, Ruler, Monitor, CheckCircle, AlertCircle, RefreshCw, Eye, EyeOff } from 'lucide-react';
import { api } from '../services/api';
import { WebcamView } from '../components/WebcamView';
import type { CalibrationData, FrameMessage, TrackingData } from '../types';

interface CalibrationProps {
  frameData?: FrameMessage | null;
  trackingData?: TrackingData | null;
}

export const Calibration: React.FC<CalibrationProps> = ({ frameData = null, trackingData = null }) => {
  const [calibData, setCalibData] = useState<CalibrationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Form states
  const [refDistance, setRefDistance] = useState<number>(60.0);
  const [screenWidth, setScreenWidth] = useState<number>(34.5);
  const [screenHeight, setScreenHeight] = useState<number>(19.4);
  const [cameraOffsetX, setCameraOffsetX] = useState<number>(0.0);
  const [cameraOffsetY, setCameraOffsetY] = useState<number>(0.5);

  const fetchCalibration = async () => {
    try {
      const data = await api.getCalibration();
      setCalibData(data);
      if (data.reference_distance_cm) setRefDistance(data.reference_distance_cm);
      if (data.screen_width_cm) setScreenWidth(data.screen_width_cm);
      if (data.screen_height_cm) setScreenHeight(data.screen_height_cm);
      if (data.camera_offset_cm && data.camera_offset_cm.length >= 2) {
        setCameraOffsetX(data.camera_offset_cm[0]);
        setCameraOffsetY(data.camera_offset_cm[1]);
      }
    } catch (err: any) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchCalibration();
  }, []);

  const handleStartCheckerboard = async () => {
    try {
      setLoading(true);
      const res = await api.startCalibration({ type: 'checkerboard', board_size: [9, 6], square_size_mm: 25.0 });
      setFeedback({ type: 'success', message: res.message || 'Checkerboard session started.' });
      await fetchCalibration();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleCaptureFrame = async () => {
    try {
      setLoading(true);
      const res = await api.captureCalibrationFrame();
      if (res.status === 'captured') {
        setFeedback({ type: 'success', message: res.message || 'Checkerboard frame captured!' });
      } else {
        setFeedback({ type: 'error', message: res.message || 'No checkerboard detected in current view.' });
      }
      await fetchCalibration();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleCalculateCalibration = async () => {
    try {
      setLoading(true);
      const res = await api.calculateCalibration();
      setFeedback({ type: 'success', message: res.message || 'Intrinsic camera calibration calculated!' });
      await fetchCalibration();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleResetCalibration = async () => {
    try {
      setLoading(true);
      await api.resetCalibration();
      setFeedback({ type: 'success', message: 'Calibration parameters reset to defaults.' });
      await fetchCalibration();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveReferenceDistance = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      const res = await api.setReferenceDistance(refDistance);
      setFeedback({ type: 'success', message: res.message || 'Reference distance scale calibrated successfully!' });
      await fetchCalibration();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  const handleSaveScreenGeometry = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setLoading(true);
      const res = await api.setScreenGeometry(screenWidth, screenHeight, [cameraOffsetX, cameraOffsetY, 0]);
      setFeedback({ type: 'success', message: res.message || 'Screen geometry saved successfully!' });
      await fetchCalibration();
    } catch (err: any) {
      setFeedback({ type: 'error', message: err.message });
    } finally {
      setLoading(false);
    }
  };

  const faceDetected = trackingData?.face?.detected ?? false;
  const currentFaceDistance = trackingData?.face?.distance_cm;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Page Title */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Camera & Spatial Calibration</h2>
          <p className="text-xs text-[#9BA7B5]">
            Configure physical reference distances, screen geometry, and intrinsic camera matrices
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchCalibration}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#181D24] text-[#9BA7B5] hover:text-[#E8EDF4] border border-[#2A313B] rounded-lg text-xs transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Feedback Alert */}
      {feedback && (
        <div
          className={`p-3.5 rounded-lg text-xs flex items-center justify-between border ${
            feedback.type === 'success'
              ? 'bg-[#37C98B]/10 text-[#37C98B] border-[#37C98B]/30'
              : 'bg-[#FF5C65]/10 text-[#FF5C65] border-[#FF5C65]/30'
          }`}
        >
          <div className="flex items-center gap-2.5">
            {feedback.type === 'success' ? (
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
            )}
            <span className="font-medium">{feedback.message}</span>
          </div>
          <button
            onClick={() => setFeedback(null)}
            className="text-[10px] uppercase font-mono px-2 py-0.5 rounded hover:bg-white/10"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Calibration Status Overview Banner */}
      <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <div
            className={`w-12 h-12 rounded-xl flex items-center justify-center border ${
              calibData?.is_calibrated
                ? 'bg-[#37C98B]/15 text-[#37C98B] border-[#37C98B]/40'
                : 'bg-[#FFB547]/15 text-[#FFB547] border-[#FFB547]/40'
            }`}
          >
            <Crosshair className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-sm">System Calibration:</h3>
              <span
                className={`text-xs font-mono px-2 py-0.5 rounded font-bold ${
                  calibData?.is_calibrated
                    ? 'bg-[#37C98B]/20 text-[#37C98B]'
                    : 'bg-[#FFB547]/20 text-[#FFB547]'
                }`}
              >
                {calibData?.is_calibrated ? 'CALIBRATED' : 'UNCALIBRATED'}
              </span>
              {calibData?.calibration_type && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#101318] border border-[#2A313B] text-[#53B7FF]">
                  Mode: {calibData.calibration_type}
                </span>
              )}
            </div>
            <p className="text-xs text-[#9BA7B5] mt-1 space-x-2">
              <span>
                Focal Length:{' '}
                <strong className="font-mono text-[#E8EDF4]">
                  {calibData?.focal_length_px?.toFixed(1) ?? '—'} px
                </strong>
              </span>
              <span>•</span>
              <span>
                Ref Distance:{' '}
                <strong className="font-mono text-[#E8EDF4]">
                  {calibData?.reference_distance_cm ? `${calibData.reference_distance_cm} cm` : 'Default'}
                </strong>
              </span>
              {calibData?.reprojection_error != null && (
                <>
                  <span>•</span>
                  <span>
                    RMS Error:{' '}
                    <strong className="font-mono text-[#37C98B]">
                      {calibData.reprojection_error.toFixed(4)}
                    </strong>
                  </span>
                </>
              )}
            </p>
          </div>
        </div>

        <button
          onClick={handleResetCalibration}
          disabled={loading}
          className="text-xs text-[#FF5C65] hover:bg-[#FF5C65]/10 px-3 py-1.5 rounded-lg border border-[#FF5C65]/30 transition-colors"
        >
          Reset to Factory Defaults
        </button>
      </div>

      {/* Main Grid: Live Camera Stream + Calibration Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Live Visual Alignment */}
        <div className="space-y-4">
          <div className="bg-[#181D24] p-4 rounded-xl border border-[#2A313B] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-wider font-semibold text-[#9BA7B5]">
                Live Calibration Camera Feed
              </span>
              <div className="flex items-center gap-1.5 text-xs font-mono">
                {faceDetected ? (
                  <span className="flex items-center gap-1 text-[#37C98B]">
                    <Eye className="w-3.5 h-3.5" /> Face Detected
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[#FFB547]">
                    <EyeOff className="w-3.5 h-3.5" /> Awaiting Face
                  </span>
                )}
              </div>
            </div>

            <WebcamView frameData={frameData} trackingData={trackingData} />

            <div className="flex items-center justify-between bg-[#101318] p-3 rounded-lg border border-[#2A313B]/80 font-mono text-xs">
              <span className="text-[#9BA7B5]">Current Estimated Distance:</span>
              <span className="text-[#53B7FF] font-bold text-sm">
                {currentFaceDistance != null ? `${currentFaceDistance.toFixed(1)} cm` : '—'}
              </span>
            </div>
          </div>

          {/* Section 2: Screen Physical Geometry */}
          <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] space-y-4">
            <div className="flex items-center gap-2.5 text-[#37C98B]">
              <Monitor className="w-5 h-5" />
              <h3 className="text-sm font-semibold text-[#E8EDF4]">2. Workstation Screen Geometry</h3>
            </div>
            <p className="text-xs text-[#9BA7B5] leading-relaxed">
              Configure physical display dimensions to map camera-relative 3D coordinates into true screen-plane positions.
            </p>

            <form onSubmit={handleSaveScreenGeometry} className="space-y-3 pt-1">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-[#9BA7B5] block mb-1">Screen Width (cm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={screenWidth}
                    onChange={(e) => setScreenWidth(parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-3 py-2 text-sm font-mono text-[#E8EDF4] focus:outline-none focus:border-[#37C98B]"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-[#9BA7B5] block mb-1">Screen Height (cm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={screenHeight}
                    onChange={(e) => setScreenHeight(parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-3 py-2 text-sm font-mono text-[#E8EDF4] focus:outline-none focus:border-[#37C98B]"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-[#9BA7B5] block mb-1">Camera X Offset (cm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={cameraOffsetX}
                    onChange={(e) => setCameraOffsetX(parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-3 py-2 text-sm font-mono text-[#E8EDF4] focus:outline-none focus:border-[#37C98B]"
                  />
                </div>
                <div>
                  <label className="text-xs font-medium text-[#9BA7B5] block mb-1">Camera Y Offset (cm)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={cameraOffsetY}
                    onChange={(e) => setCameraOffsetY(parseFloat(e.target.value) || 0)}
                    className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-3 py-2 text-sm font-mono text-[#E8EDF4] focus:outline-none focus:border-[#37C98B]"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-[#37C98B] text-[#101318] hover:bg-[#37C98B]/90 font-semibold py-2 px-4 rounded-lg text-xs transition-colors flex items-center justify-center gap-2"
              >
                <CheckCircle className="w-3.5 h-3.5" />
                <span>Save Screen Geometry</span>
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Calibration Actions */}
        <div className="space-y-6">
          {/* Section 1: Known Reference Distance Scale */}
          <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] space-y-4">
            <div className="flex items-center gap-2.5 text-[#53B7FF]">
              <Ruler className="w-5 h-5" />
              <h3 className="text-sm font-semibold text-[#E8EDF4]">1. Reference Distance Scale (Recommended)</h3>
            </div>
            <p className="text-xs text-[#9BA7B5] leading-relaxed">
              Sit at a known physical distance from your camera (e.g. 50 or 60 cm measured with a ruler). SpaceSense captures your current facial landmark pixels and computes an exact physical scaling coefficient.
            </p>

            <form onSubmit={handleSaveReferenceDistance} className="space-y-3 pt-2">
              <div>
                <label className="text-xs font-medium text-[#9BA7B5] block mb-1">
                  Known Physical Distance from Camera (cm)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="0.5"
                    min="25"
                    max="150"
                    value={refDistance}
                    onChange={(e) => setRefDistance(parseFloat(e.target.value) || 0)}
                    className="flex-1 bg-[#101318] border border-[#2A313B] rounded-lg px-3 py-2 text-sm font-mono text-[#E8EDF4] focus:outline-none focus:border-[#53B7FF]"
                  />
                  <div className="flex gap-1.5">
                    {[50, 60, 70].map((d) => (
                      <button
                        key={d}
                        type="button"
                        onClick={() => setRefDistance(d)}
                        className={`px-2.5 py-2 text-xs font-mono rounded border transition-all ${
                          refDistance === d
                            ? 'bg-[#53B7FF] text-[#101318] font-bold border-[#53B7FF]'
                            : 'bg-[#101318] text-[#9BA7B5] border-[#2A313B] hover:text-[#E8EDF4]'
                        }`}
                      >
                        {d}cm
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="p-3 bg-[#101318] rounded-lg border border-[#2A313B]/80 text-xs space-y-1">
                <div className="flex justify-between text-[#9BA7B5]">
                  <span>Face Landmark Status:</span>
                  <span className={faceDetected ? 'text-[#37C98B] font-bold' : 'text-[#FF5C65] font-bold'}>
                    {faceDetected ? 'Visible in View' : 'Not Detected'}
                  </span>
                </div>
                <div className="flex justify-between text-[#9BA7B5]">
                  <span>Current Raw Estimate:</span>
                  <span className="font-mono text-[#E8EDF4]">
                    {currentFaceDistance != null ? `${currentFaceDistance.toFixed(1)} cm` : '—'}
                  </span>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading || !faceDetected}
                className="w-full bg-[#53B7FF] text-[#101318] hover:bg-[#53B7FF]/90 font-semibold py-2.5 px-4 rounded-lg text-xs transition-colors flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <Crosshair className="w-3.5 h-3.5" />
                <span>Record & Calibrate Reference Scale</span>
              </button>
            </form>
          </div>

          {/* Section 3: Full Checkerboard Intrinsic Matrix */}
          <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5 text-[#FFB547]">
                <Camera className="w-5 h-5" />
                <h3 className="text-sm font-semibold text-[#E8EDF4]">3. OpenCV Checkerboard Intrinsic Calibration</h3>
              </div>
              <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#101318] border border-[#2A313B] text-[#FFB547]">
                Frames: <strong>{calibData?.frames_captured || 0}</strong> / 10
              </span>
            </div>
            <p className="text-xs text-[#9BA7B5] leading-relaxed">
              Hold a standard 9×6 inner-corner checkerboard pattern at different angles in front of the camera. When corners are detected, capture at least 5 frames to compute the camera intrinsic matrix.
            </p>

            <div className="space-y-3 pt-1">
              <div className="flex flex-wrap items-center gap-2.5">
                <button
                  type="button"
                  onClick={handleStartCheckerboard}
                  disabled={loading}
                  className="px-3.5 py-2 bg-[#2A313B] hover:bg-[#3B4452] text-xs font-semibold rounded-lg transition-colors"
                >
                  Start New Session
                </button>
                <button
                  type="button"
                  onClick={handleCaptureFrame}
                  disabled={loading}
                  className="px-3.5 py-2 bg-[#53B7FF]/20 text-[#53B7FF] border border-[#53B7FF]/40 hover:bg-[#53B7FF]/30 text-xs font-semibold rounded-lg transition-colors"
                >
                  Capture Current View
                </button>
                <button
                  type="button"
                  onClick={handleCalculateCalibration}
                  disabled={loading || (calibData?.frames_captured || 0) < 5}
                  className="px-3.5 py-2 bg-[#37C98B] text-[#101318] hover:bg-[#37C98B]/90 text-xs font-semibold rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Compute Intrinsic Matrix
                </button>
              </div>

              {(calibData?.frames_captured || 0) > 0 && (
                <div className="w-full bg-[#101318] rounded-full h-1.5 overflow-hidden">
                  <div
                    className="bg-[#37C98B] h-full transition-all duration-300"
                    style={{
                      width: `${Math.min(100, ((calibData?.frames_captured || 0) / 10) * 100)}%`,
                    }}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

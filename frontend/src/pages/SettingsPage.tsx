import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Camera, Sliders, Shield, CheckCircle, Eye } from 'lucide-react';
import { api } from '../services/api';
import type { AppSettings } from '../types';

export const SettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<AppSettings>({
    filter_type: 'one_euro',
    smoothing_alpha: 0.3,
    distance_thresholds: {
      too_close_cm: 35.0,
      warning_close_cm: 50.0,
      normal_min_cm: 50.0,
      normal_max_cm: 70.0,
      warning_far_cm: 75.0,
      too_far_cm: 90.0,
    },
    draw_landmarks: true,
    draw_distances: true,
    draw_ergonomic_state: true,
    frame_skip: 0,
    auto_save_interval_sec: 30.0,
    webcam_device_index: 0,
    resolution: [640, 480],
  });

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    api.getSettings().then((s) => {
      if (s) setSettings(s);
    }).catch(console.error);
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSaving(true);
      await api.updateSettings(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Title */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">System & Algorithmic Settings</h2>
          <p className="text-xs text-[#9BA7B5]">Tune camera resolution, temporal filter cutoffs & ergonomic distance boundaries</p>
        </div>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Section 1: Camera & Acquisition */}
        <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] space-y-4">
          <div className="flex items-center gap-2.5 text-[#53B7FF]">
            <Camera className="w-5 h-5" />
            <h3 className="text-sm font-semibold text-[#E8EDF4]">Camera Hardware & Resolution</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-[#9BA7B5] block mb-1.5">Camera Device Index</label>
              <select
                value={settings.webcam_device_index}
                onChange={(e) => setSettings({ ...settings, webcam_device_index: parseInt(e.target.value) || 0 })}
                className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-3 py-2 text-xs text-[#E8EDF4]"
              >
                <option value={0}>Camera 0 (Default Webcam)</option>
                <option value={1}>Camera 1 (External USB)</option>
                <option value={2}>Camera 2</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-[#9BA7B5] block mb-1.5">Acquisition Resolution</label>
              <select
                value={`${settings.resolution[0]}x${settings.resolution[1]}`}
                onChange={(e) => {
                  const parts = e.target.value.split('x').map(Number);
                  setSettings({ ...settings, resolution: [parts[0], parts[1]] });
                }}
                className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-3 py-2 text-xs text-[#E8EDF4]"
              >
                <option value="640x480">640 × 480 (Recommended for 30+ FPS)</option>
                <option value="1280x720">1280 × 720 (HD 720p)</option>
                <option value="1920x1080">1920 × 1080 (FHD 1080p)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Section 2: Temporal Filtering Algorithms */}
        <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] space-y-4">
          <div className="flex items-center gap-2.5 text-[#37C98B]">
            <Sliders className="w-5 h-5" />
            <h3 className="text-sm font-semibold text-[#E8EDF4]">Temporal Signal Filtering</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-medium text-[#9BA7B5] block mb-1.5">Filter Algorithm</label>
              <select
                value={settings.filter_type}
                onChange={(e) => setSettings({ ...settings, filter_type: e.target.value })}
                className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-3 py-2 text-xs text-[#E8EDF4]"
              >
                <option value="one_euro">1€ (One Euro) Adaptive Cutoff Filter (Recommended)</option>
                <option value="ema">Exponential Moving Average (EMA)</option>
                <option value="kalman">1D Linear Kalman Filter</option>
              </select>
              <p className="text-[11px] text-[#9BA7B5] mt-1">
                One Euro dynamically adjusts cutoff: high smoothing at rest, zero lag during rapid hand movements.
              </p>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="text-xs font-medium text-[#9BA7B5]">Smoothing Factor (Alpha)</label>
                <span className="text-xs font-mono text-[#37C98B]">{settings.smoothing_alpha}</span>
              </div>
              <input
                type="range"
                min="0.05"
                max="0.95"
                step="0.05"
                value={settings.smoothing_alpha}
                onChange={(e) => setSettings({ ...settings, smoothing_alpha: parseFloat(e.target.value) })}
                className="w-full accent-[#37C98B]"
              />
              <div className="flex justify-between text-[10px] text-[#9BA7B5] mt-1">
                <span>Heavy Smoothing (0.05)</span>
                <span>Fast Tracking (0.95)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Ergonomic Postural Distance Thresholds */}
        <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] space-y-4">
          <div className="flex items-center gap-2.5 text-[#FFB547]">
            <SettingsIcon className="w-5 h-5" />
            <h3 className="text-sm font-semibold text-[#E8EDF4]">Ergonomic Distance Thresholds (cm)</h3>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-xs font-medium text-[#9BA7B5] block mb-1">Critical Minimum (&lt; cm)</label>
              <input
                type="number"
                value={settings.distance_thresholds.too_close_cm}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    distance_thresholds: {
                      ...settings.distance_thresholds,
                      too_close_cm: parseFloat(e.target.value) || 35,
                    },
                  })
                }
                className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-3 py-2 text-xs font-mono text-[#FF5C65]"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-[#9BA7B5] block mb-1">Warning Threshold (&lt; cm)</label>
              <input
                type="number"
                value={settings.distance_thresholds.warning_close_cm}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    distance_thresholds: {
                      ...settings.distance_thresholds,
                      warning_close_cm: parseFloat(e.target.value) || 50,
                    },
                  })
                }
                className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-3 py-2 text-xs font-mono text-[#FFB547]"
              />
            </div>

            <div>
              <label className="text-xs font-medium text-[#9BA7B5] block mb-1">Comfortable Max (cm)</label>
              <input
                type="number"
                value={settings.distance_thresholds.normal_max_cm}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    distance_thresholds: {
                      ...settings.distance_thresholds,
                      normal_max_cm: parseFloat(e.target.value) || 70,
                    },
                  })
                }
                className="w-full bg-[#101318] border border-[#2A313B] rounded-lg px-3 py-2 text-xs font-mono text-[#37C98B]"
              />
            </div>
          </div>
        </div>

        {/* Section 4: Privacy & Security */}
        <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B] space-y-3">
          <div className="flex items-center gap-2.5 text-[#53B7FF]">
            <Shield className="w-5 h-5" />
            <h3 className="text-sm font-semibold text-[#E8EDF4]">Privacy & Local Computing Guarantee</h3>
          </div>
          <p className="text-xs text-[#9BA7B5] leading-relaxed">
            SpaceSense AI processes 100% of video frames locally on your computer using OpenCV and MediaPipe. No webcam streams, raw images, or biometric landmarks are ever transmitted to cloud servers or stored externally.
          </p>
        </div>

        {/* Submit Button */}
        <div className="flex items-center justify-end gap-3 pt-2">
          {saved && (
            <span className="text-xs text-[#37C98B] flex items-center gap-1 font-mono">
              <CheckCircle className="w-4 h-4" />
              Settings saved!
            </span>
          )}
          <button
            type="submit"
            disabled={saving}
            className="px-6 py-2.5 bg-[#53B7FF] text-[#101318] hover:bg-[#53B7FF]/90 font-bold rounded-lg text-xs transition-colors"
          >
            {saving ? 'Saving...' : 'Apply & Save Settings'}
          </button>
        </div>
      </form>
    </div>
  );
};

import React, { useState, useEffect } from 'react';
import { Compass, Gauge, Move, Navigation, Activity, Hand } from 'lucide-react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import { WebcamView } from '../components/WebcamView';
import { TrajectoryCanvas } from '../components/TrajectoryCanvas';
import { AngleDisplay } from '../components/AngleDisplay';
import { MetricCard } from '../components/MetricCard';
import type { TrackingData, FrameMessage } from '../types';

interface MotionAnalysisProps {
  trackingData: TrackingData | null;
  frameData: FrameMessage | null;
}

export const MotionAnalysis: React.FC<MotionAnalysisProps> = ({ trackingData, frameData }) => {
  const [selectedHandLabel, setSelectedHandLabel] = useState<'Right' | 'Left'>('Right');
  const hands = trackingData?.hands || [];

  const hasLeftHand = hands.some((h) => h.label === 'Left' && h.detected);
  const hasRightHand = hands.some((h) => h.label === 'Right' && h.detected);

  // Automatically sync hand selector when only one hand is in view
  useEffect(() => {
    if (hasLeftHand && !hasRightHand && selectedHandLabel !== 'Left') {
      setSelectedHandLabel('Left');
    } else if (hasRightHand && !hasLeftHand && selectedHandLabel !== 'Right') {
      setSelectedHandLabel('Right');
    }
  }, [hasLeftHand, hasRightHand, selectedHandLabel]);

  // Pick target hand: chosen hand first, fallback to any detected hand
  const primaryHand =
    hands.find((h) => h.label === selectedHandLabel && h.detected) ||
    hands.find((h) => h.detected) ||
    hands[0];

  const activeAngle =
    primaryHand?.hand_body_angle && typeof primaryHand.hand_body_angle.angle_deg === 'number'
      ? primaryHand.hand_body_angle
      : trackingData?.hand_body_angle && typeof trackingData.hand_body_angle.angle_deg === 'number'
      ? trackingData.hand_body_angle
      : null;

  // Motion history for speed chart
  const [speedHistory, setSpeedHistory] = useState<{ frame: number; speed: number }[]>([]);
  const [directionCounts, setDirectionCounts] = useState<Record<string, number>>({
    UP: 0,
    DOWN: 0,
    LEFT: 0,
    RIGHT: 0,
  });

  useEffect(() => {
    if (primaryHand?.movement) {
      const speed = primaryHand.movement.speed_px_per_sec;
      setSpeedHistory((prev) => {
        const next = [...prev, { frame: prev.length, speed }];
        return next.slice(-40);
      });

      const dir = primaryHand.orientation_direction?.toUpperCase();
      if (dir && directionCounts[dir] !== undefined) {
        setDirectionCounts((prev) => ({
          ...prev,
          [dir]: prev[dir] + 1,
        }));
      }
    }
  }, [primaryHand]);

  const dirBarData = [
    { dir: 'UP', count: directionCounts.UP },
    { dir: 'DOWN', count: directionCounts.DOWN },
    { dir: 'LEFT', count: directionCounts.LEFT },
    { dir: 'RIGHT', count: directionCounts.RIGHT },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header with Hand Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Kinematic & Motion Analysis</h2>
          <p className="text-xs text-[#9BA7B5]">
            Real-time hand camera feed, 2D trajectory tracking, velocity profiles & joint angles
          </p>
        </div>

        {/* Hand Selector Buttons & Target Info */}
        <div className="flex items-center gap-3">
          <div className="flex items-center bg-[#181D24] p-1 rounded-lg border border-[#2A313B]">
            <button
              onClick={() => setSelectedHandLabel('Left')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
                selectedHandLabel === 'Left'
                  ? 'bg-[#53B7FF] text-[#101318] font-semibold shadow-sm'
                  : 'text-[#9BA7B5] hover:text-[#E2E8F0]'
              }`}
            >
              <Hand className="w-3.5 h-3.5" />
              Left Hand {hasLeftHand ? '•' : ''}
            </button>
            <button
              onClick={() => setSelectedHandLabel('Right')}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-medium transition-all ${
                selectedHandLabel === 'Right'
                  ? 'bg-[#53B7FF] text-[#101318] font-semibold shadow-sm'
                  : 'text-[#9BA7B5] hover:text-[#E2E8F0]'
              }`}
            >
              <Hand className="w-3.5 h-3.5" />
              Right Hand {hasRightHand ? '•' : ''}
            </button>
          </div>

          <div className="flex items-center gap-2 font-mono text-xs text-[#53B7FF] bg-[#181D24] px-3 py-1.5 rounded-lg border border-[#2A313B]">
            <Activity className="w-4 h-4 text-[#37C98B]" />
            <span>Target: {primaryHand ? `${primaryHand.label} Hand` : 'Awaiting Hand'}</span>
          </div>
        </div>
      </div>

      {/* Top Metrics Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          title="Instantaneous Velocity"
          value={primaryHand?.movement?.speed_px_per_sec?.toFixed(1) ?? '0.0'}
          unit="px/s"
          icon={Gauge}
        />
        <MetricCard
          title="Heading Angle"
          value={primaryHand?.movement?.direction_deg?.toFixed(1) ?? '—'}
          unit="deg"
          icon={Navigation}
          subtitle="atan2(dy, dx)"
        />
        <MetricCard
          title="Hand Plane Rotation"
          value={primaryHand?.orientation_deg?.toFixed(1) ?? '—'}
          unit="deg"
          icon={Compass}
          subtitle={`Heading: ${primaryHand?.orientation_direction?.toUpperCase() ?? '—'}`}
        />
        <MetricCard
          title="Odometer"
          value={primaryHand?.movement?.cumulative_distance?.toFixed(0) ?? '0'}
          unit="px"
          icon={Move}
          subtitle="Cumulative Travel"
        />
      </div>

      {/* Visual Tracking: Camera Feed & Kinematic Trajectory */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Live Camera View with Landmark HUD */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider font-semibold text-[#9BA7B5]">
              Live Tracking Stream
            </span>
            <span className="text-xs font-mono text-[#53B7FF]">Real-Time Overlay</span>
          </div>
          <WebcamView frameData={frameData} trackingData={trackingData} />
        </div>

        {/* Real-time Trajectory Canvas */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wider font-semibold text-[#9BA7B5]">
              Motion Path & Trajectory
            </span>
            <span className="text-xs font-mono text-[#37C98B]">2D XY Kinematics</span>
          </div>
          <TrajectoryCanvas
            hands={hands}
            cameraResolution={trackingData?.camera_resolution}
            activeHandLabel={primaryHand?.label}
          />
        </div>
      </div>

      {/* Speed / Velocity Chart & Direction Histogram */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Velocity Profile */}
        <div className="lg:col-span-2 bg-[#181D24] p-4 rounded-xl border border-[#2A313B]">
          <div className="flex justify-between items-center mb-3">
            <span className="text-xs uppercase tracking-wider font-semibold text-[#9BA7B5]">
              Velocity Profile (v = Δp/Δt)
            </span>
            <span className="text-xs font-mono text-[#37C98B]">Real-Time Speed</span>
          </div>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={speedHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2A313B" opacity={0.5} />
                <XAxis dataKey="frame" hide />
                <YAxis stroke="#9BA7B5" fontSize={10} tickFormatter={(v) => `${v}`} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#181D24',
                    borderColor: '#2A313B',
                    fontSize: '11px',
                    borderRadius: '8px',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="speed"
                  stroke="#37C98B"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Right 1 Col: Direction Cardinal Histogram */}
        <div className="bg-[#181D24] p-4 rounded-xl border border-[#2A313B]">
          <div className="flex justify-between items-center mb-3">
            <span className="text-xs uppercase tracking-wider font-semibold text-[#9BA7B5]">
              Direction Histogram
            </span>
            <span className="text-xs font-mono text-[#53B7FF]">Cardinal Frequency</span>
          </div>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dirBarData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2A313B" opacity={0.4} />
                <XAxis dataKey="dir" stroke="#9BA7B5" fontSize={11} />
                <YAxis stroke="#9BA7B5" fontSize={10} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#181D24',
                    borderColor: '#2A313B',
                    fontSize: '11px',
                    borderRadius: '8px',
                  }}
                />
                <Bar dataKey="count" fill="#53B7FF" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Whole Hand vs Body Symmetry Angle */}
      <div>
        <AngleDisplay
          handBodyAngle={activeAngle}
          handLabel={primaryHand?.label}
        />
      </div>
    </div>
  );
};

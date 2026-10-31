import React from 'react';
import { Eye, Hand, ShieldAlert, Compass, Gauge, Zap } from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import { WebcamView } from '../components/WebcamView';
import { DistanceGauge } from '../components/DistanceGauge';
import { MetricCard } from '../components/MetricCard';
import { AngleDisplay } from '../components/AngleDisplay';
import type { TrackingData, FrameMessage } from '../types';

interface LiveMonitorProps {
  trackingData: TrackingData | null;
  frameData: FrameMessage | null;
  history: { timestamp: number; distance: number | null; fps: number }[];
}

export const LiveMonitor: React.FC<LiveMonitorProps> = ({ trackingData, frameData, history }) => {
  const face = trackingData?.face;
  const hands = trackingData?.hands || [];
  const ergo = trackingData?.ergonomic;
  const closest = trackingData?.closest_object;

  const leftHand = hands.find((h) => h.label === 'Left');
  const rightHand = hands.find((h) => h.label === 'Right');
  const activeHand = rightHand || leftHand;

  const activeAngle =
    activeHand?.hand_body_angle && typeof activeHand.hand_body_angle.angle_deg === 'number'
      ? activeHand.hand_body_angle
      : trackingData?.hand_body_angle && typeof trackingData.hand_body_angle.angle_deg === 'number'
      ? trackingData.hand_body_angle
      : null;

  // Chart data
  const chartData = history.map((pt, i) => ({
    time: i,
    distance: pt.distance,
    comfortableMax: 70,
    comfortableMin: 50,
    critical: 35,
  }));

  const ergoStatus = ergo?.state === 'CRITICAL' ? 'critical' : ergo?.state === 'WARNING' ? 'warning' : 'normal';

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Banner: Ergonomic Status alert */}
      {ergo && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between transition-all ${
            ergo.state === 'CRITICAL'
              ? 'bg-[#FF5C65]/15 border-[#FF5C65]/40 text-[#FF5C65]'
              : ergo.state === 'WARNING'
              ? 'bg-[#FFB547]/15 border-[#FFB547]/40 text-[#FFB547]'
              : 'bg-[#37C98B]/10 border-[#37C98B]/30 text-[#37C98B]'
          }`}
        >
          <div className="flex items-center gap-3">
            <ShieldAlert className="w-5 h-5 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold tracking-wide">
                ERGONOMIC POSTURE: {ergo.state}
              </p>
              <p className="text-xs opacity-80">
                {ergo.state === 'CRITICAL'
                  ? 'Screen is critically close (<35cm). Please push back workstation.'
                  : ergo.state === 'WARNING'
                  ? 'Approaching minimum recommended distance (<50cm).'
                  : 'User is within the recommended ergonomic focal range (50–70cm).'}
              </p>
            </div>
          </div>
          <div className="text-right font-mono text-xs">
            <p>Warnings: {ergo.warning_count}</p>
            <p>Time: {ergo.time_in_state_sec.toFixed(0)}s</p>
          </div>
        </div>
      )}

      {/* Main Grid: Stream & Real-time Gauges */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Webcam Stream */}
        <div className="lg:col-span-2 space-y-4">
          <WebcamView frameData={frameData} trackingData={trackingData} />

          {/* Temporal Distance Chart */}
          <div className="bg-[#181D24] p-4 rounded-xl border border-[#2A313B]">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs uppercase tracking-wider font-semibold text-[#9BA7B5]">
                Face Distance Trend (Last 60 Frames)
              </span>
              <span className="text-xs font-mono text-[#53B7FF]">Real-Time Geometry</span>
            </div>
            <div className="h-44 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2A313B" opacity={0.6} />
                  <XAxis dataKey="time" hide />
                  <YAxis domain={[20, 100]} stroke="#9BA7B5" fontSize={10} tickFormatter={(v) => `${v}cm`} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#181D24', borderColor: '#2A313B', fontSize: '11px', borderRadius: '8px' }}
                    labelStyle={{ display: 'none' }}
                  />
                  <Line type="monotone" dataKey="distance" stroke="#53B7FF" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <Line type="monotone" dataKey="comfortableMin" stroke="#37C98B" strokeWidth={1} strokeDasharray="4 4" dot={false} />
                  <Line type="monotone" dataKey="comfortableMax" stroke="#37C98B" strokeWidth={1} strokeDasharray="4 4" dot={false} />
                  <Line type="monotone" dataKey="critical" stroke="#FF5C65" strokeWidth={1} strokeDasharray="4 4" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Right 1 Col: Metric Gauges & Panels */}
        <div className="space-y-4">
          <DistanceGauge distance={face?.distance_cm ?? null} label="Face Distance" />

          {/* Metric Cards Grid */}
          <div className="grid grid-cols-2 gap-3">
            <MetricCard
              title="Closest Object"
              value={closest?.name ?? 'None'}
              subtitle={closest ? `${closest.distance_cm.toFixed(1)} cm` : undefined}
              icon={Zap}
              status={closest?.distance_cm && closest.distance_cm < 40 ? 'warning' : 'default'}
            />

            <MetricCard
              title="Postural State"
              value={ergo?.state ?? 'NORMAL'}
              icon={ShieldAlert}
              status={ergoStatus}
            />

            <MetricCard
              title="Left Hand Dist"
              value={leftHand?.distance_cm ? leftHand.distance_cm.toFixed(1) : null}
              unit="cm"
              icon={Hand}
              subtitle={leftHand?.detected ? 'Detected' : 'Inactive'}
            />

            <MetricCard
              title="Right Hand Dist"
              value={rightHand?.distance_cm ? rightHand.distance_cm.toFixed(1) : null}
              unit="cm"
              icon={Hand}
              subtitle={rightHand?.detected ? 'Detected' : 'Inactive'}
            />

            <MetricCard
              title="Hand Direction"
              value={activeHand?.orientation_direction?.toUpperCase() ?? '—'}
              subtitle={activeHand?.orientation_deg ? `${activeHand.orientation_deg}° rotation` : undefined}
              icon={Compass}
            />

            <MetricCard
              title="Hand Speed"
              value={activeHand?.movement?.speed_px_per_sec ?? 0}
              unit="px/s"
              icon={Gauge}
            />
          </div>

          {/* Whole Hand & Body Symmetry Angle */}
          <AngleDisplay
            handBodyAngle={activeAngle}
            handLabel={activeHand?.label}
          />
        </div>
      </div>
    </div>
  );
};

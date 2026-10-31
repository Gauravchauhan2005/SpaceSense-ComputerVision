import React from 'react';
import { Compass, Activity, ArrowUpRight, CheckCircle2, AlertTriangle, ShieldCheck } from 'lucide-react';
import type { HandBodyAngleData } from '../types';

interface AngleDisplayProps {
  handBodyAngle?: HandBodyAngleData | null;
  handLabel?: string;
  // Kept for backward compatibility if passed
  angles?: Record<string, Record<string, number>> | null;
}

export const AngleDisplay: React.FC<AngleDisplayProps> = ({ handBodyAngle, handLabel }) => {
  const hasAngle = handBodyAngle != null && typeof handBodyAngle.angle_deg === 'number' && !isNaN(handBodyAngle.angle_deg);
  const angle = hasAngle ? handBodyAngle.angle_deg : 0;
  const acuteAngle = hasAngle ? (handBodyAngle.acute_angle_deg ?? angle) : 0;
  const direction = hasAngle ? (handBodyAngle.lateral_direction ?? 'aligned') : 'aligned';

  const displayTarget = handLabel
    ? (handLabel.toLowerCase().includes('hand') ? handLabel : `${handLabel} Hand`)
    : 'Active Hand';

  // Biomechanical posture evaluation
  let postureStatus = 'Neutral Alignment';
  let postureColor = 'text-[#37C98B]';
  let postureBg = 'bg-[#37C98B]/10 border-[#37C98B]/30';
  let postureDesc = 'Hand is in a relaxed posture close to the body vertical axis (<35°).';
  let PostureIcon = ShieldCheck;

  if (angle >= 35 && angle < 75) {
    postureStatus = 'Working Zone';
    postureColor = 'text-[#53B7FF]';
    postureBg = 'bg-[#53B7FF]/10 border-[#53B7FF]/30';
    postureDesc = 'Hand is in an active workstation reaching angle (35°–75°).';
    PostureIcon = CheckCircle2;
  } else if (angle >= 75) {
    postureStatus = 'High Elevation';
    postureColor = 'text-[#FFB547]';
    postureBg = 'bg-[#FFB547]/10 border-[#FFB547]/30';
    postureDesc = 'Significant arm/hand elevation. Monitor shoulder fatigue (>75°).';
    PostureIcon = AlertTriangle;
  }

  // SVG Geometry visualization (Protractor center at 100, 100)
  const cx = 100;
  const cy = 100;
  const radius = 65;

  // Body symmetry axis points vertically downward (angle 90° in standard SVG coordinates, where Y is down)
  const symX2 = cx;
  const symY2 = cy + radius;

  // Hand vector rotated by angle:
  // If direction is left: rotated counter-clockwise (-angle)
  // If direction is right: rotated clockwise (+angle)
  const sign = direction === 'left' ? -1 : 1;
  const rad = ((90 + sign * angle) * Math.PI) / 180;
  const handX = cx + radius * Math.cos(rad);
  const handY = cy + radius * Math.sin(rad);

  // SVG arc for the included angle
  const arcRadius = 32;
  const arcStartAngle = 90 * (Math.PI / 180);
  const arcStartX = cx + arcRadius * Math.cos(arcStartAngle);
  const arcStartY = cy + arcRadius * Math.sin(arcStartAngle);
  const arcEndX = cx + arcRadius * Math.cos(rad);
  const arcEndY = cy + arcRadius * Math.sin(rad);
  const largeArcFlag = angle > 180 ? 1 : 0;
  const sweepFlag = sign > 0 ? 1 : 0;
  const arcPath = `M ${arcStartX} ${arcStartY} A ${arcRadius} ${arcRadius} 0 ${largeArcFlag} ${sweepFlag} ${arcEndX} ${arcEndY}`;

  return (
    <div className="bg-[#181D24] p-5 rounded-xl border border-[#2A313B]">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-[#2A313B]/80 gap-2">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-[#53B7FF]/15 text-[#53B7FF] border border-[#53B7FF]/30">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold tracking-tight text-[#E8EDF4]">
              Whole Hand & Body Symmetry Angle
            </h3>
            <p className="text-[11px] text-[#9BA7B5]">
              Real-time geometric angle between body sagittal midline & whole hand axis
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 font-mono text-xs">
          <span className="text-[11px] px-2 py-0.5 rounded bg-[#101318] border border-[#2A313B] text-[#53B7FF]">
            Target: {displayTarget}
          </span>
          <span className="text-[10px] text-[#9BA7B5] px-1.5 py-0.5 rounded bg-[#101318] border border-[#2A313B]/60">
            arccos(v_sym · v_hand)
          </span>
        </div>
      </div>

      {hasAngle ? (
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 pt-4 items-center">
          {/* Left Column: Big Angle Readout & Biomechanical Metrics */}
          <div className="md:col-span-7 space-y-4">
            <div className="flex items-baseline gap-3">
              <span className="text-4xl font-extrabold tracking-tight font-mono text-[#E8EDF4]">
                {angle.toFixed(1)}°
              </span>
              <span className="text-xs font-mono uppercase tracking-wider text-[#9BA7B5]">
                Included Angle
              </span>
            </div>

            {/* Posture Status Alert */}
            <div className={`p-3 rounded-lg border flex items-start gap-2.5 ${postureBg}`}>
              <PostureIcon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${postureColor}`} />
              <div>
                <p className={`text-xs font-bold ${postureColor}`}>
                  {postureStatus} ({angle < 35 ? '<35°' : angle < 75 ? '35°–75°' : '>75°'})
                </p>
                <p className="text-[11px] text-[#E8EDF4]/80 mt-0.5 leading-relaxed">
                  {postureDesc}
                </p>
              </div>
            </div>

            {/* Metric Pills */}
            <div className="grid grid-cols-3 gap-2 pt-1 font-mono text-xs">
              <div className="bg-[#101318] p-2.5 rounded-lg border border-[#2A313B]/70">
                <span className="text-[10px] text-[#9BA7B5] block mb-0.5">Acute Angle</span>
                <span className="text-xs font-bold text-[#53B7FF]">{acuteAngle.toFixed(1)}°</span>
              </div>
              <div className="bg-[#101318] p-2.5 rounded-lg border border-[#2A313B]/70">
                <span className="text-[10px] text-[#9BA7B5] block mb-0.5">Lateral Side</span>
                <span className="text-xs font-bold capitalize text-[#37C98B]">{direction}</span>
              </div>
              <div className="bg-[#101318] p-2.5 rounded-lg border border-[#2A313B]/70">
                <span className="text-[10px] text-[#9BA7B5] block mb-0.5">Reference Line</span>
                <span className="text-xs font-bold text-[#FFB547]">Sagittal Midline</span>
              </div>
            </div>
          </div>

          {/* Right Column: Geometric SVG Diagram */}
          <div className="md:col-span-5 flex flex-col items-center justify-center bg-[#101318] p-3 rounded-xl border border-[#2A313B]/80">
            <svg viewBox="0 0 200 200" className="w-48 h-48 select-none">
              {/* Outer Protractor Guide Circle */}
              <circle cx={cx} cy={cy} r={radius} fill="none" stroke="#2A313B" strokeWidth="1" strokeDasharray="3 3" />
              <circle cx={cx} cy={cy} r={arcRadius} fill="none" stroke="#2A313B" strokeWidth="1" opacity="0.6" />

              {/* Ticks at 0, 45, 90, 135, 180 */}
              <line x1={cx} y1={cy - radius} x2={cx} y2={cy + radius} stroke="#2A313B" strokeWidth="1" strokeDasharray="2 2" />
              <line x1={cx - radius} y1={cy} x2={cx + radius} y2={cy} stroke="#2A313B" strokeWidth="1" strokeDasharray="2 2" />

              {/* Angle Sector Arc */}
              {angle > 2 && (
                <path d={arcPath} fill="none" stroke="#37C98B" strokeWidth="2.5" strokeLinecap="round" opacity="0.85" />
              )}

              {/* Body Symmetry Reference Line (Cyan) */}
              <line
                x1={cx}
                y1={cy - radius + 10}
                x2={symX2}
                y2={symY2}
                stroke="#53B7FF"
                strokeWidth="2.5"
                strokeDasharray="4 3"
              />
              <circle cx={cx} cy={cy - radius + 10} r="3" fill="#53B7FF" />
              <text x={cx + 6} y={cy - radius + 14} fill="#53B7FF" fontSize="8" fontFamily="monospace">
                Head
              </text>
              <text x={symX2 + 6} y={symY2 - 4} fill="#53B7FF" fontSize="8" fontFamily="monospace">
                Body Midline
              </text>

              {/* Center Pivot Point (Wrist / Body origin) */}
              <circle cx={cx} cy={cy} r="4" fill="#E8EDF4" stroke="#181D24" strokeWidth="1.5" />

              {/* Whole Hand Longitudinal Vector (Lime) */}
              <line
                x1={cx}
                y1={cy}
                x2={handX}
                y2={handY}
                stroke="#37C98B"
                strokeWidth="3.5"
                strokeLinecap="round"
              />
              <circle cx={handX} cy={handY} r="4" fill="#37C98B" />
              <text
                x={handX + (sign > 0 ? 6 : -36)}
                y={handY - 6}
                fill="#37C98B"
                fontSize="8"
                fontFamily="monospace"
                fontWeight="bold"
              >
                Fingertip
              </text>

              {/* Angle value badge inside diagram */}
              <rect x={cx - 18} y={cy + 12} width="36" height="15" rx="3" fill="#181D24" stroke="#2A313B" />
              <text
                x={cx}
                y={cy + 23}
                textAnchor="middle"
                fill="#E8EDF4"
                fontSize="9"
                fontFamily="monospace"
                fontWeight="bold"
              >
                {angle.toFixed(0)}°
              </text>
            </svg>

            {/* Diagram Legend */}
            <div className="flex items-center gap-4 text-[10px] font-mono mt-1 text-[#9BA7B5]">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#53B7FF]" />
                <span>Body Midline</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-[#37C98B]" />
                <span>Whole Hand</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-[#9BA7B5] space-y-1.5">
          <Activity className="w-8 h-8 mx-auto text-[#9BA7B5]/40 animate-pulse" />
          <p className="text-xs font-medium">Awaiting Hand & Face Alignment</p>
          <p className="text-[11px] text-[#9BA7B5]/60 max-w-sm mx-auto">
            Ensure your upper body and hand are visible in the webcam view to calculate the angle against the body symmetry axis.
          </p>
        </div>
      )}
    </div>
  );
};

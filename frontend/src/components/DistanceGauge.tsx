import React from 'react';

interface DistanceGaugeProps {
  distance: number | null;
  min?: number;
  max?: number;
  label?: string;
}

export const DistanceGauge: React.FC<DistanceGaugeProps> = ({
  distance,
  min = 20,
  max = 100,
  label = 'Face Distance',
}) => {
  // Comfortable: 50-70cm (Green)
  // Warning: 35-50cm (Yellow)
  // Critical: <35cm (Red)
  const clamped = distance !== null ? Math.min(Math.max(distance, min), max) : min;
  const percentage = ((clamped - min) / (max - min)) * 100;

  let color = '#37C98B'; // normal
  let zoneText = 'COMFORTABLE (50–70 cm)';

  if (distance === null) {
    color = '#9BA7B5';
    zoneText = 'NO TARGET DETECTED';
  } else if (distance < 35) {
    color = '#FF5C65';
    zoneText = 'TOO CLOSE (< 35 cm)';
  } else if (distance < 50) {
    color = '#FFB547';
    zoneText = 'CLOSE WARNING (< 50 cm)';
  } else if (distance > 75) {
    color = '#53B7FF';
    zoneText = 'FAR (> 75 cm)';
  }

  return (
    <div className="bg-[#181D24] p-4 rounded-xl border border-[#2A313B]">
      <div className="flex justify-between items-center mb-2">
        <span className="text-xs uppercase tracking-wider font-semibold text-[#9BA7B5]">{label}</span>
        <span className="text-xs font-mono font-medium px-2 py-0.5 rounded" style={{ color, backgroundColor: `${color}15` }}>
          {zoneText}
        </span>
      </div>

      <div className="flex items-baseline gap-2 mb-3">
        <span className="text-3xl font-bold font-mono" style={{ color }}>
          {distance !== null ? distance.toFixed(1) : '—'}
        </span>
        <span className="text-sm font-mono text-[#9BA7B5]">cm</span>
      </div>

      {/* Progress / Range bar */}
      <div className="relative w-full h-3 bg-[#101318] rounded-full overflow-hidden border border-[#2A313B]">
        {/* Background color zones */}
        {/* Critical zone: 20-35cm -> ~18.75% */}
        <div className="absolute left-0 top-0 bottom-0 bg-[#FF5C65]/20" style={{ width: `${((35 - min) / (max - min)) * 100}%` }} />
        {/* Warning zone: 35-50cm */}
        <div
          className="absolute top-0 bottom-0 bg-[#FFB547]/20"
          style={{
            left: `${((35 - min) / (max - min)) * 100}%`,
            width: `${((50 - 35) / (max - min)) * 100}%`,
          }}
        />
        {/* Good zone: 50-70cm */}
        <div
          className="absolute top-0 bottom-0 bg-[#37C98B]/20"
          style={{
            left: `${((50 - min) / (max - min)) * 100}%`,
            width: `${((70 - 50) / (max - min)) * 100}%`,
          }}
        />

        {/* Current position indicator */}
        {distance !== null && (
          <div
            className="absolute top-0 bottom-0 w-2 rounded-full shadow-lg transition-all duration-150"
            style={{
              left: `calc(${percentage}% - 4px)`,
              backgroundColor: color,
              boxShadow: `0 0 10px ${color}`,
            }}
          />
        )}
      </div>

      {/* Scale markers */}
      <div className="flex justify-between text-[10px] font-mono text-[#9BA7B5] mt-1.5 px-0.5">
        <span>{min}cm</span>
        <span>35cm</span>
        <span>50cm</span>
        <span>70cm</span>
        <span>{max}cm</span>
      </div>
    </div>
  );
};

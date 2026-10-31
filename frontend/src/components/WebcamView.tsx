import React, { useEffect, useRef } from 'react';
import { Camera, CameraOff, Eye, Hand } from 'lucide-react';
import type { FrameMessage, TrackingData, ErgonomicState } from '../types';

interface WebcamViewProps {
  frameData: FrameMessage | null;
  trackingData: TrackingData | null;
  className?: string;
}

export const WebcamView: React.FC<WebcamViewProps> = ({ frameData, trackingData, className = '' }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!frameData || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const image = new Image();
    image.onload = () => {
      canvas.width = image.width;
      canvas.height = image.height;
      ctx.drawImage(image, 0, 0);
    };
    image.src = `data:image/jpeg;base64,${frameData.data}`;
  }, [frameData]);

  const state: ErgonomicState = trackingData?.ergonomic?.state || 'NORMAL';
  let borderColor = 'border-[#2A313B]';
  if (state === 'WARNING') borderColor = 'border-[#FFB547]';
  if (state === 'CRITICAL') borderColor = 'border-[#FF5C65]';

  const faceDetected = trackingData?.face?.detected ?? false;
  const handsCount = trackingData?.hands?.filter((h) => h.detected).length ?? 0;

  return (
    <div className={`relative bg-[#101318] rounded-xl overflow-hidden border-2 ${borderColor} shadow-2xl transition-all duration-300 ${className}`}>
      {frameData ? (
        <canvas ref={canvasRef} className="w-full h-auto block object-contain" />
      ) : (
        <div className="w-full aspect-video flex flex-col items-center justify-center text-[#9BA7B5] bg-[#181D24]/40">
          <CameraOff className="w-12 h-12 mb-3 text-[#9BA7B5]/50 animate-pulse" />
          <p className="text-sm font-medium">Awaiting Video Stream...</p>
          <p className="text-xs text-[#9BA7B5]/60 mt-1">Start camera in Controls or check backend connection</p>
        </div>
      )}

      {/* Top Left: Tracking HUD badges */}
      <div className="absolute top-3 left-3 flex items-center gap-2 z-10">
        <span
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium backdrop-blur-md border ${
            faceDetected
              ? 'bg-[#37C98B]/20 text-[#37C98B] border-[#37C98B]/40'
              : 'bg-[#181D24]/80 text-[#9BA7B5] border-[#2A313B]'
          }`}
        >
          <Eye className="w-3.5 h-3.5" />
          {faceDetected ? `FACE: ${trackingData?.face?.distance_cm?.toFixed(0) || '—'}cm` : 'NO FACE'}
        </span>

        <span
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium backdrop-blur-md border ${
            handsCount > 0
              ? 'bg-[#53B7FF]/20 text-[#53B7FF] border-[#53B7FF]/40'
              : 'bg-[#181D24]/80 text-[#9BA7B5] border-[#2A313B]'
          }`}
        >
          <Hand className="w-3.5 h-3.5" />
          {handsCount > 0 ? `HANDS (${handsCount})` : 'NO HANDS'}
        </span>
      </div>

      {/* Top Right: Real-time FPS & Latency */}
      {trackingData && (
        <div className="absolute top-3 right-3 flex items-center gap-2 z-10">
          <span className="bg-[#181D24]/80 backdrop-blur-md text-[#E8EDF4] border border-[#2A313B] px-2.5 py-1 rounded-md text-xs font-mono">
            {trackingData.fps.toFixed(1)} <span className="text-[#9BA7B5]">FPS</span>
          </span>
          <span className="bg-[#181D24]/80 backdrop-blur-md text-[#E8EDF4] border border-[#2A313B] px-2.5 py-1 rounded-md text-xs font-mono">
            {trackingData.processing_time_ms.toFixed(0)} <span className="text-[#9BA7B5]">ms</span>
          </span>
        </div>
      )}

      {/* Bottom overlay: Ergonomic Status Banner */}
      {trackingData?.ergonomic && (
        <div
          className={`absolute bottom-0 inset-x-0 py-1.5 px-4 text-xs font-mono font-semibold flex items-center justify-between backdrop-blur-md ${
            state === 'CRITICAL'
              ? 'bg-[#FF5C65]/30 text-[#FF5C65] border-t border-[#FF5C65]/40'
              : state === 'WARNING'
              ? 'bg-[#FFB547]/30 text-[#FFB547] border-t border-[#FFB547]/40'
              : 'bg-[#37C98B]/20 text-[#37C98B] border-t border-[#37C98B]/30'
          }`}
        >
          <span>STATUS: {state}</span>
          <span>Time in state: {trackingData.ergonomic.time_in_state_sec.toFixed(0)}s</span>
          <span>Warnings: {trackingData.ergonomic.warning_count}</span>
        </div>
      )}
    </div>
  );
};

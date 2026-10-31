import React, { useEffect, useRef, useState } from 'react';
import { RotateCcw, Crosshair } from 'lucide-react';
import type { SingleHandData } from '../types';

interface TrajectoryCanvasProps {
  hands: SingleHandData[];
  cameraResolution?: [number, number] | null;
  activeHandLabel?: string;
  className?: string;
}

export const TrajectoryCanvas: React.FC<TrajectoryCanvasProps> = ({
  hands,
  cameraResolution,
  activeHandLabel,
  className = '',
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const trailsRef = useRef<Map<string, { x: number; y: number; time: number }[]>>(new Map());
  const [totalPoints, setTotalPoints] = useState<number>(0);

  // Clear trails handler
  const handleClear = () => {
    trailsRef.current.clear();
    setTotalPoints(0);
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext('2d');
      if (ctx) {
        ctx.fillStyle = '#101318';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }
    }
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const canvasW = canvas.width;
    const canvasH = canvas.height;
    const now = Date.now();

    // Map hand coordinates to canvas space with robust resolution normalization
    hands.forEach((hand) => {
      if (hand.detected && (hand.center || hand.center_normalized)) {
        let normX = 0.5;
        let normY = 0.5;

        if (hand.center_normalized && hand.center_normalized.length === 2) {
          normX = hand.center_normalized[0];
          normY = hand.center_normalized[1];
        } else if (hand.center && hand.center.length === 2) {
          const cx = hand.center[0];
          const cy = hand.center[1];

          if (cx <= 1.0 && cy <= 1.0) {
            normX = cx;
            normY = cy;
          } else if (cameraResolution && cameraResolution[0] > 0 && cameraResolution[1] > 0) {
            normX = cx / cameraResolution[0];
            normY = cy / cameraResolution[1];
          } else if (cx > 1000) {
            // Typical 1080p stream
            normX = cx / 1920;
            normY = cy / 1080;
          } else if (cx > 640) {
            // Typical 720p stream
            normX = cx / 1280;
            normY = cy / 720;
          } else {
            // Typical 480p stream
            normX = cx / 640;
            normY = cy / 480;
          }
        }

        // Clamp to [0, 1]
        normX = Math.max(0.01, Math.min(0.99, normX));
        normY = Math.max(0.01, Math.min(0.99, normY));

        const canvasX = normX * canvasW;
        const canvasY = normY * canvasH;

        const key = hand.label || 'Hand';
        if (!trailsRef.current.has(key)) {
          trailsRef.current.set(key, []);
        }
        const trail = trailsRef.current.get(key)!;
        trail.push({ x: canvasX, y: canvasY, time: now });

        // Keep last 60 trajectory points or within 4 seconds
        while (trail.length > 70 || (trail.length > 0 && now - trail[0].time > 4000)) {
          trail.shift();
        }
      }
    });

    // Update point count
    let ptsCount = 0;
    trailsRef.current.forEach((t) => (ptsCount += t.length));
    setTotalPoints(ptsCount);

    // ── 1. Clear & Background ──
    ctx.fillStyle = '#101318';
    ctx.fillRect(0, 0, canvasW, canvasH);

    // ── 2. Grid & Kinematic Coordinates ──
    ctx.lineWidth = 1;
    const step = 40;

    // Minor grid
    ctx.strokeStyle = 'rgba(42, 49, 59, 0.4)';
    for (let x = step; x < canvasW; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvasH);
      ctx.stroke();
    }
    for (let y = step; y < canvasH; y += step) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvasW, y);
      ctx.stroke();
    }

    // Center Crosshairs
    const midX = canvasW / 2;
    const midY = canvasH / 2;
    ctx.strokeStyle = 'rgba(83, 183, 255, 0.25)';
    ctx.setLineDash([4, 4]);

    ctx.beginPath();
    ctx.moveTo(midX, 0);
    ctx.lineTo(midX, canvasH);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(canvasW, midY);
    ctx.stroke();

    ctx.setLineDash([]);

    // Concentric Range Rings
    ctx.strokeStyle = 'rgba(42, 49, 59, 0.5)';
    [60, 120, 180].forEach((r) => {
      ctx.beginPath();
      ctx.arc(midX, midY, r, 0, Math.PI * 2);
      ctx.stroke();
    });

    // Axis coordinate markers
    ctx.fillStyle = '#4A5568';
    ctx.font = '9px JetBrains Mono, monospace';
    ctx.fillText('(0,0)', 6, 12);
    ctx.fillText(`(${canvasW},${canvasH})`, canvasW - 55, canvasH - 6);
    ctx.fillText('Origin', midX + 4, midY - 4);

    // ── 3. Render Hand Trails ──
    let anyHandRendered = false;

    trailsRef.current.forEach((trail, label) => {
      if (trail.length === 0) return;
      anyHandRendered = true;

      const isRight = label === 'Right';
      const isActive = !activeHandLabel || activeHandLabel === label;

      // Color scheme: Right Hand = Electric Blue (#53B7FF), Left Hand = Gold/Amber (#FFB547)
      const rgbBase = isRight ? '83, 183, 255' : '255, 181, 71';
      const hexBase = isRight ? '#53B7FF' : '#FFB547';

      // Draw path segments
      if (trail.length > 1) {
        for (let i = 1; i < trail.length; i++) {
          const p1 = trail[i - 1];
          const p2 = trail[i];
          const progress = i / trail.length;
          const alpha = Math.max(0.15, progress * (isActive ? 0.95 : 0.45));

          ctx.save();
          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.strokeStyle = `rgba(${rgbBase}, ${alpha})`;
          ctx.lineWidth = isActive ? 1.5 + progress * 3.5 : 1.5;
          ctx.lineCap = 'round';
          ctx.lineJoin = 'round';

          if (isActive && progress > 0.5) {
            ctx.shadowColor = `rgba(${rgbBase}, 0.8)`;
            ctx.shadowBlur = 8;
          }
          ctx.stroke();
          ctx.restore();
        }
      }

      // Draw Head Marker
      const head = trail[trail.length - 1];

      ctx.save();
      // Outer halo pulse
      ctx.beginPath();
      ctx.arc(head.x, head.y, isActive ? 10 : 7, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(${rgbBase}, 0.4)`;
      ctx.lineWidth = 2;
      ctx.stroke();

      // Solid inner core with glow
      ctx.beginPath();
      ctx.arc(head.x, head.y, isActive ? 5 : 4, 0, Math.PI * 2);
      ctx.fillStyle = hexBase;
      ctx.shadowColor = `rgba(${rgbBase}, 1.0)`;
      ctx.shadowBlur = 12;
      ctx.fill();
      ctx.restore();

      // Coordinate & Hand Label
      ctx.save();
      ctx.font = '10px JetBrains Mono, monospace';
      ctx.fillStyle = hexBase;
      const labelText = `${label} Hand (${Math.round(head.x)}, ${Math.round(head.y)})`;
      ctx.fillText(labelText, Math.min(canvasW - 130, head.x + 12), Math.max(16, head.y - 6));
      ctx.restore();
    });

    // ── 4. Empty State Watermark if no hand is tracked ──
    if (!anyHandRendered || ptsCount === 0) {
      ctx.save();
      ctx.fillStyle = 'rgba(155, 167, 181, 0.4)';
      ctx.font = '12px JetBrains Mono, monospace';
      ctx.textAlign = 'center';
      ctx.fillText('Awaiting Hand Detection & Kinematic Trail...', midX, midY - 10);
      ctx.font = '10px Inter, sans-serif';
      ctx.fillStyle = 'rgba(155, 167, 181, 0.3)';
      ctx.fillText('Move hand in webcam view to track 2D motion trajectory', midX, midY + 12);
      ctx.restore();
    }
  }, [hands, cameraResolution, activeHandLabel]);

  return (
    <div className={`relative bg-[#181D24] p-4 rounded-xl border border-[#2A313B] ${className}`}>
      {/* Top Header */}
      <div className="flex justify-between items-center mb-2.5">
        <div className="flex items-center gap-2">
          <Crosshair className="w-4 h-4 text-[#53B7FF]" />
          <span className="text-xs uppercase tracking-wider font-semibold text-[#E2E8F0]">
            2D Motion Trajectory
          </span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#101318] border border-[#2A313B] text-[#53B7FF]">
            {totalPoints > 0 ? `${totalPoints} Points Active` : 'Idle'}
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleClear}
            className="flex items-center gap-1 px-2.5 py-1 text-[11px] font-mono text-[#9BA7B5] hover:text-[#FF5C65] hover:bg-[#FF5C65]/10 rounded border border-[#2A313B] transition-all"
            title="Reset trajectory trail"
          >
            <RotateCcw className="w-3 h-3" />
            Reset Trail
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div className="relative overflow-hidden rounded-lg border border-[#2A313B]/80 shadow-inner">
        <canvas
          ref={canvasRef}
          width={640}
          height={360}
          className="w-full h-auto block bg-[#101318] object-contain"
        />
      </div>
    </div>
  );
};

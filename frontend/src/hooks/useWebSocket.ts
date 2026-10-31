// ============================================================================
// SpaceSense AI — useWebSocket Hook
// ============================================================================

import { useEffect, useState, useRef } from 'react';
import { wsService } from '../services/websocket';
import type { TrackingData, FrameMessage, ConnectionStatus } from '../types';

export function useWebSocket() {
  const [trackingData, setTrackingData] = useState<TrackingData | null>(null);
  const [frameData, setFrameData] = useState<FrameMessage | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>(wsService.status);
  const [history, setHistory] = useState<{ timestamp: number; distance: number | null; fps: number }[]>([]);

  useEffect(() => {
    wsService.connect();

    const unsubTracking = wsService.onTracking((data) => {
      setTrackingData(data);
      if (data.face?.distance_cm !== undefined) {
        setHistory((prev) => {
          const next = [
            ...prev,
            {
              timestamp: data.timestamp,
              distance: data.face.distance_cm ?? null,
              fps: data.fps,
            },
          ];
          return next.slice(-60); // keep last 60 data points (~2 seconds at 30fps)
        });
      }
    });

    const unsubFrame = wsService.onFrame((data) => {
      setFrameData(data);
    });

    const unsubStatus = wsService.onStatus((s) => {
      setStatus(s);
    });

    return () => {
      unsubTracking();
      unsubFrame();
      unsubStatus();
    };
  }, []);

  return {
    trackingData,
    frameData,
    status,
    history,
  };
}

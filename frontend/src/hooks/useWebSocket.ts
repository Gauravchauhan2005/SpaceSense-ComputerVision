// ============================================================================
// SpaceSense AI — useWebSocket Hook
// ============================================================================

import { useEffect, useState, useRef } from 'react';
import { wsService } from '../services/websocket';
import { clientVision } from '../services/clientVision';
import type { TrackingData, FrameMessage, ConnectionStatus } from '../types';

export function useWebSocket() {
  const [trackingData, setTrackingData] = useState<TrackingData | null>(null);
  const [frameData, setFrameData] = useState<FrameMessage | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>(wsService.status);
  const [history, setHistory] = useState<{ timestamp: number; distance: number | null; fps: number }[]>([]);
  const [isClientStreaming, setIsClientStreaming] = useState(false);

  useEffect(() => {
    wsService.connect();

    const unsubTracking = wsService.onTracking((data) => {
      // Prioritize live backend frames if they have active detected metrics
      if (!isClientStreaming || data.fps > 0) {
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
            return next.slice(-60);
          });
        }
      }
    });

    const unsubFrame = wsService.onFrame((data) => {
      if (!isClientStreaming) {
        setFrameData(data);
      }
    });

    const unsubStatus = wsService.onStatus((s) => {
      setStatus(s);
    });

    // Wire up clientVision pipeline
    clientVision.setCallbacks(
      (data) => {
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
            return next.slice(-60);
          });
        }
      },
      (jpegBase64, w, h) => {
        setFrameData({
          type: 'frame',
          data: jpegBase64,
          width: w,
          height: h,
        });
      }
    );

    return () => {
      unsubTracking();
      unsubFrame();
      unsubStatus();
    };
  }, [isClientStreaming]);

  const startClientCamera = async () => {
    await clientVision.start();
    setIsClientStreaming(true);
    setStatus('connected');
  };

  const stopClientCamera = () => {
    clientVision.stop();
    setIsClientStreaming(false);
  };

  return {
    trackingData,
    frameData,
    status,
    history,
    isClientStreaming,
    startClientCamera,
    stopClientCamera,
  };
}

// ============================================================================
// SpaceSense AI — WebSocket Service
// ============================================================================

import type { TrackingData, FrameMessage, ConnectionStatus } from '../types';

type TrackingHandler = (data: TrackingData) => void;
type FrameHandler = (data: FrameMessage) => void;
type StatusHandler = (status: ConnectionStatus) => void;

export class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 30;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionallyClosed = false;

  private trackingHandlers: Set<TrackingHandler> = new Set();
  private frameHandlers: Set<FrameHandler> = new Set();
  private statusHandlers: Set<StatusHandler> = new Set();

  private _status: ConnectionStatus = 'disconnected';

  constructor(url?: string) {
    if (url) {
      this.url = url;
    } else if (import.meta.env.VITE_WS_BASE) {
      const base = import.meta.env.VITE_WS_BASE.replace(/\/$/, '');
      this.url = `${base}/ws/tracking`;
    } else {
      const loc = window.location;
      const wsProtocol = loc.protocol === 'https:' ? 'wss:' : 'ws:';
      // In Vite dev mode, port might be 5173 which proxies to 8000, or directly port 8000
      this.url = `${wsProtocol}//${loc.hostname}:8000/ws/tracking`;
    }
  }

  get status(): ConnectionStatus {
    return this._status;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    this.intentionallyClosed = false;
    this.setStatus('connecting');
    this.createConnection();
  }

  disconnect(): void {
    this.intentionallyClosed = true;
    this.clearReconnectTimer();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('disconnected');
  }

  onTracking(handler: TrackingHandler): () => void {
    this.trackingHandlers.add(handler);
    return () => { this.trackingHandlers.delete(handler); };
  }

  onFrame(handler: FrameHandler): () => void {
    this.frameHandlers.add(handler);
    return () => { this.frameHandlers.delete(handler); };
  }

  onStatus(handler: StatusHandler): () => void {
    this.statusHandlers.add(handler);
    return () => { this.statusHandlers.delete(handler); };
  }

  private createConnection(): void {
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.setStatus('connected');
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'tracking_data') {
            this.trackingHandlers.forEach((h) => h(msg as TrackingData));
          } else if (msg.type === 'frame') {
            this.frameHandlers.forEach((h) => h(msg as FrameMessage));
          }
        } catch {
          // ignore parse errors
        }
      };

      this.ws.onclose = () => {
        this.ws = null;
        if (!this.intentionallyClosed) {
          this.setStatus('disconnected');
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        this.setStatus('error');
      };
    } catch {
      this.setStatus('error');
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return;

    const delay = Math.min(1000 * Math.pow(1.5, this.reconnectAttempts), 10000);
    this.reconnectAttempts++;

    this.reconnectTimer = setTimeout(() => {
      this.createConnection();
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private setStatus(status: ConnectionStatus): void {
    this._status = status;
    this.statusHandlers.forEach((h) => h(status));
  }
}

export const wsService = new WebSocketService();

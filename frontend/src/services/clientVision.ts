// ============================================================================
// SpaceSense AI — Real-Time Client-Side Computer Vision Engine
// Runs official Google MediaPipe Tasks Vision (FaceLandmarker & HandLandmarker)
// directly in the user's browser via WebAssembly / WebGL!
// ============================================================================

import {
  FilesetResolver,
  FaceLandmarker,
  HandLandmarker,
} from '@mediapipe/tasks-vision';
import type {
  TrackingData,
  SingleHandData,
  FaceData,
  HandBodyAngleData,
  ErgonomicState,
} from '../types';

export class ClientVisionPipeline {
  private video: HTMLVideoElement | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private stream: MediaStream | null = null;
  private animFrameId: number | null = null;
  private isRunning: boolean = false;

  private faceLandmarker: FaceLandmarker | null = null;
  private handLandmarker: HandLandmarker | null = null;
  private isModelLoading: boolean = false;

  private onTrackingCallback: ((data: TrackingData) => void) | null = null;
  private onFrameCallback: ((jpegBase64: string, w: number, h: number) => void) | null = null;

  // Ergonomic temporal smoothing
  private smoothedDistance: number = 60.0;
  private stateStartTime: number = Date.now();
  private currentState: ErgonomicState = 'NORMAL';
  private warningCount: number = 0;
  private criticalCount: number = 0;

  // Kinematic motion tracking (velocity & odometer)
  private prevHandCenter: { x: number; y: number } | null = null;
  private prevHandTime: number = 0;
  private cumulativeDistance: number = 0;
  private smoothedSpeed: number = 0;

  // Rolling FPS
  private frameCount: number = 0;
  private lastFpsTime: number = Date.now();
  private currentFps: number = 30.0;

  constructor() {
    this.video = document.createElement('video');
    this.video.playsInline = true;
    this.video.muted = true;
    this.canvas = document.createElement('canvas');
  }

  public setCallbacks(
    onTracking: (data: TrackingData) => void,
    onFrame: (jpegBase64: string, w: number, h: number) => void
  ) {
    this.onTrackingCallback = onTracking;
    this.onFrameCallback = onFrame;
  }

  public async start(): Promise<void> {
    if (this.isRunning) return;

    // 1. Initialize MediaPipe WebAssembly models if not yet loaded
    if (!this.faceLandmarker || !this.handLandmarker) {
      await this.loadModels();
    }

    // 2. Request camera stream
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: 'user',
        },
        audio: false,
      });

      if (!this.video) return;
      this.video.srcObject = this.stream;
      await this.video.play();

      this.isRunning = true;
      this.loop();
    } catch (err: any) {
      console.error('Error accessing webcam:', err);
      throw new Error(err.message || 'Webcam access failed');
    }
  }

  public stop(): void {
    this.isRunning = false;
    if (this.animFrameId) {
      cancelAnimationFrame(this.animFrameId);
      this.animFrameId = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
    if (this.video) {
      this.video.srcObject = null;
    }
  }

  private async loadModels(): Promise<void> {
    if (this.isModelLoading) return;
    this.isModelLoading = true;

    try {
      const vision = await FilesetResolver.forVisionTasks(
        'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@latest/wasm'
      );

      this.faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath:
            'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
          delegate: 'GPU',
        },
        outputFaceBlendshapes: false,
        runningMode: 'VIDEO',
        numFaces: 1,
        minFaceDetectionConfidence: 0.4,
        minTrackingConfidence: 0.4,
      });

      this.handLandmarker = await HandLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath:
            'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task',
          delegate: 'GPU',
        },
        runningMode: 'VIDEO',
        numHands: 2,
        minHandDetectionConfidence: 0.4,
        minTrackingConfidence: 0.4,
      });

      console.log('MediaPipe Browser Models successfully loaded!');
    } catch (err) {
      console.error('Failed to load MediaPipe WebAssembly models:', err);
    } finally {
      this.isModelLoading = false;
    }
  }

  private loop = () => {
    if (!this.isRunning || !this.video || !this.canvas) return;

    const vw = this.video.videoWidth;
    const vh = this.video.videoHeight;

    if (vw > 0 && vh > 0) {
      this.canvas.width = vw;
      this.canvas.height = vh;
      const ctx = this.canvas.getContext('2d');

      if (ctx) {
        const tStart = performance.now();
        const nowMs = performance.now();

        // Mirrored selfie draw
        ctx.save();
        ctx.scale(-1, 1);
        ctx.drawImage(this.video, -vw, 0, vw, vh);
        ctx.restore();

        // 1. Run Face & Hand Landmark Inference
        let faceResult: any = null;
        let handResult: any = null;

        if (this.faceLandmarker) {
          try {
            faceResult = this.faceLandmarker.detectForVideo(this.canvas, nowMs);
          } catch (e) {
            // drop if frame timestamp collision
          }
        }

        if (this.handLandmarker) {
          try {
            handResult = this.handLandmarker.detectForVideo(this.canvas, nowMs);
          } catch (e) {
            // drop
          }
        }

        // 2. Draw landmarks, skeleton, body symmetry axis, and hand angles
        const tracking = this.processDetections(ctx, vw, vh, faceResult, handResult);

        // Calculate processing time
        const procMs = Math.round(performance.now() - tStart);
        tracking.processing_time_ms = procMs;

        // FPS calculation
        this.frameCount++;
        const now = Date.now();
        if (now - this.lastFpsTime >= 500) {
          this.currentFps = (this.frameCount * 1000) / (now - this.lastFpsTime);
          this.frameCount = 0;
          this.lastFpsTime = now;
        }
        tracking.fps = Math.round(this.currentFps);

        // 3. Emit Frame to canvas/subscriber
        const dataUrl = this.canvas.toDataURL('image/jpeg', 0.75);
        const base64 = dataUrl.split(',')[1];
        if (this.onFrameCallback) {
          this.onFrameCallback(base64, vw, vh);
        }

        // 4. Emit Tracking Metrics
        if (this.onTrackingCallback) {
          this.onTrackingCallback(tracking);
        }
      }
    }

    this.animFrameId = requestAnimationFrame(this.loop);
  };

  private processDetections(
    ctx: CanvasRenderingContext2D,
    w: number,
    h: number,
    faceResult: any,
    handResult: any
  ): TrackingData {
    let faceData: FaceData = { detected: false };
    let handsPayload: SingleHandData[] = [];
    let handBodyAngle: HandBodyAngleData | null = null;
    let faceDistCm: number | null = null;

    // ── Face Processing & Geometric Distance Estimation ────────────────
    let symOrigin: [number, number] = [w / 2, h / 2];
    let symVec: [number, number] = [0, 1];

    if (faceResult?.faceLandmarks && faceResult.faceLandmarks.length > 0) {
      const lms = faceResult.faceLandmarks[0];

      // Draw facial points
      ctx.fillStyle = '#00FFB4';
      for (let i = 0; i < lms.length; i += 8) {
        const px = lms[i].x * w;
        const py = lms[i].y * h;
        ctx.fillRect(px - 1, py - 1, 2, 2);
      }

      // Landmarks: 10 = forehead, 152 = chin, 33 = left eye outer, 263 = right eye outer
      const forehead = lms[10];
      const chin = lms[152];
      const leftEye = lms[33];
      const rightEye = lms[263];

      if (forehead && chin) {
        const dx = (chin.x - forehead.x) * w;
        const dy = (chin.y - forehead.y) * h;
        const mag = Math.hypot(dx, dy);
        if (mag > 1e-4) {
          symVec = [dx / mag, dy / mag];
          symOrigin = [chin.x * w, chin.y * h];
        }
      }

      // Pinhole camera distance estimation via Inter-Pupillary / Facial Breadth
      if (leftEye && rightEye) {
        const eyeDx = (rightEye.x - leftEye.x) * w;
        const eyeDy = (rightEye.y - leftEye.y) * h;
        const eyeSpanPx = Math.hypot(eyeDx, eyeDy);

        // Reference: Real human eye span ~6.3 cm, standard webcam focal length ~600px
        if (eyeSpanPx > 5) {
          const rawDist = (600.0 * 6.3) / eyeSpanPx;
          this.smoothedDistance = 0.8 * this.smoothedDistance + 0.2 * rawDist;
          faceDistCm = Math.round(this.smoothedDistance * 10) / 10;
        }
      }

      faceData = {
        detected: true,
        distance_cm: faceDistCm,
        confidence: 0.95,
        center: [symOrigin[0], symOrigin[1]],
        landmarks_count: lms.length,
      };
    }

    // ── Hand Processing & Kinematics ──────────────────────────────────
    let primaryHandLms: any[] | null = null;
    let primaryHandLabel: string = 'Right';

    if (handResult?.landmarks && handResult.landmarks.length > 0) {
      for (let i = 0; i < handResult.landmarks.length; i++) {
        const lms = handResult.landmarks[i];
        const handedness = handResult.handednesses?.[i]?.[0]?.categoryName || (i === 0 ? 'Right' : 'Left');
        // Mirrored correction
        const label = handedness === 'Left' ? 'Right' : 'Left';

        if (!primaryHandLms) {
          primaryHandLms = lms;
          primaryHandLabel = label;
        }

        // Draw hand skeleton
        this.drawHandSkeleton(ctx, lms, w, h);

        const wrist = lms[0];
        const middleTip = lms[12];
        const indexMcp = lms[5];
        const pinkyMcp = lms[17];

        const palmWidthPx = Math.hypot(
          (pinkyMcp.x - indexMcp.x) * w,
          (pinkyMcp.y - indexMcp.y) * h
        );

        // Hand distance via palm breadth (nominal human palm ~8.5cm)
        const handDist = palmWidthPx > 5 ? Math.round(((600.0 * 8.5) / palmWidthPx) * 10) / 10 : null;

        // Kinematics (Speed & direction)
        const handCenterX = (wrist.x + middleTip.x) * 0.5 * w;
        const handCenterY = (wrist.y + middleTip.y) * 0.5 * h;
        const nowSec = Date.now() / 1000;

        let speed = 0;
        let headingDeg = 0;
        if (this.prevHandCenter && this.prevHandTime > 0) {
          const dt = Math.max(0.001, nowSec - this.prevHandTime);
          const dDist = Math.hypot(handCenterX - this.prevHandCenter.x, handCenterY - this.prevHandCenter.y);
          const instSpeed = dDist / dt;
          this.smoothedSpeed = 0.7 * this.smoothedSpeed + 0.3 * instSpeed;
          speed = Math.round(this.smoothedSpeed);
          this.cumulativeDistance += dDist;
          headingDeg = Math.round((Math.atan2(handCenterY - this.prevHandCenter.y, handCenterX - this.prevHandCenter.x) * 180) / Math.PI);
        }
        this.prevHandCenter = { x: handCenterX, y: handCenterY };
        this.prevHandTime = nowSec;

        handsPayload.push({
          label,
          detected: true,
          distance_cm: handDist,
          center: [Math.round(handCenterX), Math.round(handCenterY)],
          center_normalized: [roundNum(wrist.x, 3), roundNum(wrist.y, 3)],
          wrist: [Math.round(wrist.x * w), Math.round(wrist.y * h)],
          palm_width_px: Math.round(palmWidthPx),
          orientation_deg: Math.round(Math.abs(headingDeg)),
          orientation_direction: headingDeg > -90 && headingDeg < 90 ? 'right' : 'left',
          movement: {
            speed_px_per_sec: speed,
            direction_deg: headingDeg,
            cumulative_distance: Math.round(this.cumulativeDistance),
          },
          confidence: 0.95,
        });
      }
    }

    // ── Whole Hand & Body Symmetry Angle Calculation ─────────────────
    if (primaryHandLms) {
      const wrist = primaryHandLms[0];
      const tip = primaryHandLms[12] || primaryHandLms[9];

      const handVecX = (tip.x - wrist.x) * w;
      const handVecY = (tip.y - wrist.y) * h;
      const magHand = Math.hypot(handVecX, handVecY);

      if (magHand > 1e-4) {
        const normHandX = handVecX / magHand;
        const normHandY = handVecY / magHand;

        // Dot product with body symmetry vector
        const dot = symVec[0] * normHandX + symVec[1] * normHandY;
        const clampedDot = Math.max(-1, Math.min(1, dot));
        const angleDeg = Math.round((Math.acos(clampedDot) * 180) / Math.PI);
        const acuteDeg = angleDeg <= 90 ? angleDeg : 180 - angleDeg;

        // Cross product for lateral direction
        const cross = symVec[0] * normHandY - symVec[1] * normHandX;
        const lateralDir = cross > 0.05 ? 'left' : cross < -0.05 ? 'right' : 'aligned';

        const lineLen = Math.max(w, h);
        const symP1: [number, number] = [
          Math.round(symOrigin[0] - symVec[0] * lineLen * 0.4),
          Math.round(symOrigin[1] - symVec[1] * lineLen * 0.4),
        ];
        const symP2: [number, number] = [
          Math.round(symOrigin[0] + symVec[0] * lineLen * 0.7),
          Math.round(symOrigin[1] + symVec[1] * lineLen * 0.7),
        ];

        handBodyAngle = {
          angle_deg: angleDeg,
          acute_angle_deg: acuteDeg,
          lateral_direction: lateralDir,
          hand_vector: [
            [Math.round(wrist.x * w), Math.round(wrist.y * h)],
            [Math.round(tip.x * w), Math.round(tip.y * h)],
          ],
          symmetry_line: [symP1, symP2],
          symmetry_origin: [Math.round(symOrigin[0]), Math.round(symOrigin[1])],
        };

        // Draw Symmetry line on canvas (Cyan)
        ctx.strokeStyle = '#53B7FF';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.moveTo(symP1[0], symP1[1]);
        ctx.lineTo(symP2[0], symP2[1]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Draw Hand Vector (Lime)
        ctx.strokeStyle = '#37C98B';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(wrist.x * w, wrist.y * h);
        ctx.lineTo(tip.x * w, tip.y * h);
        ctx.stroke();

        // Draw angle badge
        const badgeX = Math.min(w - 120, Math.max(20, (wrist.x * w + tip.x * w) / 2 + 10));
        const badgeY = Math.min(h - 20, Math.max(30, (wrist.y * h + tip.y * h) / 2 - 10));
        ctx.fillStyle = '#101318';
        ctx.fillRect(badgeX - 4, badgeY - 14, 110, 20);
        ctx.strokeStyle = '#37C98B';
        ctx.lineWidth = 1;
        ctx.strokeRect(badgeX - 4, badgeY - 14, 110, 20);
        ctx.fillStyle = '#FFFFFF';
        ctx.font = '11px monospace';
        ctx.fillText(`Angle: ${angleDeg}°`, badgeX, badgeY);
      }
    }

    // Ergonomic posture state update
    let ergoState: ErgonomicState = 'NORMAL';
    if (faceDistCm !== null) {
      if (faceDistCm < 35) ergoState = 'CRITICAL';
      else if (faceDistCm < 50) ergoState = 'WARNING';
    }

    if (ergoState !== this.currentState) {
      if (ergoState === 'WARNING') this.warningCount++;
      if (ergoState === 'CRITICAL') this.criticalCount++;
      this.currentState = ergoState;
      this.stateStartTime = Date.now();
    }

    const timeInState = (Date.now() - this.stateStartTime) / 1000;

    return {
      type: 'tracking_data',
      timestamp: Date.now() / 1000,
      frame_number: this.frameCount,
      fps: Math.round(this.currentFps),
      processing_time_ms: 20,
      camera_resolution: [w, h],
      face: faceData,
      hands: handsPayload,
      hand_body_angle: handBodyAngle,
      closest_object: handsPayload.length > 0 && handsPayload[0].distance_cm
        ? { name: `${handsPayload[0].label} Hand`, distance_cm: handsPayload[0].distance_cm }
        : faceDistCm
        ? { name: 'Face', distance_cm: faceDistCm }
        : null,
      ergonomic: {
        state: this.currentState,
        face_distance_cm: faceDistCm,
        smoothed_distance_cm: faceDistCm,
        time_in_state_sec: timeInState,
        warning_count: this.warningCount,
        critical_count: this.criticalCount,
      },
    };
  }

  private drawHandSkeleton(ctx: CanvasRenderingContext2D, lms: any[], w: number, h: number) {
    const connections = [
      [0, 1], [1, 2], [2, 3], [3, 4],       // Thumb
      [0, 5], [5, 6], [6, 7], [7, 8],       // Index
      [0, 9], [9, 10], [10, 11], [11, 12],  // Middle
      [0, 13], [13, 14], [14, 15], [15, 16],// Ring
      [0, 17], [17, 18], [18, 19], [19, 20],// Pinky
      [5, 9], [9, 13], [13, 17],            // Palm
    ];

    ctx.strokeStyle = '#FFB547';
    ctx.lineWidth = 2;
    for (const [s, e] of connections) {
      ctx.beginPath();
      ctx.moveTo(lms[s].x * w, lms[s].y * h);
      ctx.lineTo(lms[e].x * w, lms[e].y * h);
      ctx.stroke();
    }

    ctx.fillStyle = '#FF5C65';
    for (let i = 0; i < lms.length; i++) {
      ctx.beginPath();
      ctx.arc(lms[i].x * w, lms[i].y * h, 3, 0, 2 * Math.PI);
      ctx.fill();
    }
  }
}

function roundNum(n: number, decimals: number): number {
  const factor = Math.pow(10, decimals);
  return Math.round(n * factor) / factor;
}

export const clientVision = new ClientVisionPipeline();

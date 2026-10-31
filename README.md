# SpaceSense AI 🎯

**Real-Time Computer Vision, Spatial Tracking & Ergonomic Intelligence**

---

## Overview

SpaceSense AI is a privacy-first desktop application that uses your webcam and computer vision to track spatial relationships between you and your screen in real time. It detects your face and hands using MediaPipe, estimates distances with a monocular pinhole camera model, calculates joint angles, and monitors ergonomic posture — all processed locally on your machine.

The system provides live feedback through an interactive React dashboard, helping you maintain healthy screen distance habits, analyse hand movement patterns, and export session data for further research. Whether you're interested in ergonomic wellness, human-computer interaction research, or simply curious about spatial geometry, SpaceSense AI gives you a rich, real-time data stream with zero cloud dependency.

SpaceSense AI is built as a full-stack application with a FastAPI/WebSocket backend for vision processing and a Vite-powered React frontend for visualisation. Every frame captured by the camera is analysed locally; no video data ever leaves your device.

---

## Key Features

| Category | Feature |
|---|---|
| 👤 **Face Tracking** | Real-time face landmark detection (468 points via MediaPipe Face Mesh) |
| 🤚 **Hand Tracking** | Hand pose estimation with 21 landmarks per hand |
| 📏 **Distance Estimation** | Camera-relative distance via calibrated pinhole model (face & hands) |
| 📐 **Angle Calculation** | Finger joint angles, hand orientation, movement heading |
| 🏃 **Motion Analysis** | Velocity, acceleration, direction, and trajectory tracking |
| 🪑 **Ergonomic Monitoring** | Configurable distance thresholds with state machine (NORMAL / WARNING / CRITICAL) |
| 🎯 **Camera Calibration** | Checkerboard intrinsic calibration + reference-distance calibration |
| 🔌 **WebSocket Streaming** | Real-time data push to the frontend at camera frame rate |
| 📊 **React Dashboard** | Interactive 6-page dashboard with live charts and visualisations |
| 💾 **Session History** | SQLite persistence with session replay and CSV export |
| 📈 **Evaluation Metrics** | MAE, RMSE, relative error, jitter analysis |
| 🔒 **Privacy-First** | 100 % local processing — no cloud, no uploads, no telemetry |

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Computer Vision** | OpenCV 4.8+, MediaPipe 0.10+ | Camera capture, face/hand detection |
| **Math / Science** | NumPy, SciPy | Geometry, filtering, statistics |
| **Backend** | FastAPI, Uvicorn, WebSockets | REST API, real-time streaming |
| **Database** | SQLite via aiosqlite | Session storage, async I/O |
| **Frontend** | React 18, TypeScript, Vite | Interactive dashboard |
| **Charts** | Recharts / Chart.js | Real-time data visualisation |
| **Styling** | Tailwind CSS | Responsive UI |
| **Testing** | pytest, pytest-asyncio, httpx | Backend test suite |
| **Linting** | Ruff | Fast Python linter |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                       SpaceSense AI Pipeline                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────┐   ┌───────────────┐   ┌───────────────────────┐   │
│  │  Webcam  │──▶│  Frame Grab   │──▶│  MediaPipe Detection  │   │
│  │ (Camera) │   │  (OpenCV)     │   │  Face Mesh + Hands    │   │
│  └─────────┘   └───────────────┘   └──────────┬────────────┘   │
│                                                 │                │
│                    ┌────────────────────────────┼──────────┐     │
│                    │        Geometry Engine     ▼          │     │
│                    │  ┌──────────┐ ┌──────────┐ ┌───────┐ │     │
│                    │  │ Distance │ │  Angles  │ │Motion │ │     │
│                    │  │Estimator │ │Calculator│ │Tracker│ │     │
│                    │  └────┬─────┘ └────┬─────┘ └───┬───┘ │     │
│                    └───────┼────────────┼───────────┼─────┘     │
│                            │            │           │            │
│                    ┌───────▼────────────▼───────────▼─────┐     │
│                    │       Temporal Filters               │     │
│                    │  (EMA · One Euro · Kalman)           │     │
│                    └───────────────────┬──────────────────┘     │
│                                        │                        │
│           ┌────────────────────────────▼──────────────┐         │
│           │          Ergonomic Monitor                │         │
│           │   State Machine · Alerts · Time Tracking  │         │
│           └────────────────────────────┬──────────────┘         │
│                                        │                        │
│  ┌─────────────────┐   ┌──────────────▼──────────────┐         │
│  │  SQLite / CSV   │◀──│     FastAPI + WebSocket     │         │
│  │  (Persistence)  │   │  REST API · Live Streaming  │         │
│  └─────────────────┘   └──────────────┬──────────────┘         │
│                                        │                        │
└────────────────────────────────────────┼────────────────────────┘
                                         │  ws://localhost:8000/ws
                                         ▼
                              ┌─────────────────────┐
                              │   React Dashboard   │
                              │  Charts · Controls  │
                              │  History · Export    │
                              └─────────────────────┘
```

---

## Screenshots

> *Screenshots will be added after the first working release.*

---

## Installation

### Prerequisites

| Requirement | Minimum Version |
|---|---|
| Python | 3.11+ |
| Node.js | 18+ |
| Webcam | Any USB / built-in camera |

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/SpaceSenseAI.git
cd SpaceSenseAI

# 2. Backend setup
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt

# 3. Frontend setup
cd frontend
npm install
cd ..

# 4. Copy environment config
cp .env.example .env        # Linux/macOS
copy .env.example .env      # Windows

# 5. Start the backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 6. Start the frontend (new terminal)
cd frontend
npm run dev
```

### One-Command Start (Windows)

```powershell
# PowerShell
.\scripts\start.ps1

# Or with Command Prompt
scripts\start.bat
```

The script will:
1. Create a virtual environment (if needed)
2. Install all Python dependencies
3. Install frontend dependencies
4. Start both backend and frontend servers

---

## Usage

Open your browser to **http://localhost:5173** after starting both servers.

### Dashboard Pages

| Page | Description |
|---|---|
| **Live View** | Real-time camera feed with overlaid landmarks, distance, and angles |
| **Distance Monitor** | Distance-over-time chart with ergonomic zone indicators |
| **Hand Analysis** | Finger joint angles, hand orientation, movement vectors |
| **Motion Tracking** | Velocity, acceleration, and trajectory visualisation |
| **Session History** | Browse past sessions, view summaries, export to CSV |
| **Settings** | Camera selection, calibration, threshold configuration |

### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/status` | System status and current measurements |
| `GET` | `/api/sessions` | List all recorded sessions |
| `GET` | `/api/sessions/{id}` | Session details and metrics |
| `POST` | `/api/calibrate` | Trigger distance calibration |
| `GET` | `/api/export/{id}` | Export session data as CSV |
| `WS` | `/ws` | Real-time data stream (WebSocket) |

Visit **http://localhost:8000/docs** for full interactive API documentation (Swagger UI).

---

## Measurement Methods

### Distance Estimation

SpaceSense uses the **pinhole camera model** to estimate the distance between the user and the camera:

```
Z = (f × W) / w
```

| Symbol | Meaning |
|---|---|
| `Z` | Estimated distance from camera (mm) |
| `f` | Focal length of the camera (pixels) |
| `W` | Known real-world width of the reference object (mm) |
| `w` | Measured width of the object in the image (pixels) |

**For face distance**, the reference width `W` is the inter-pupillary distance (IPD), which averages ~63 mm for adults. The pixel width `w` is measured as the distance between the left and right eye landmarks detected by MediaPipe Face Mesh.

**For hand distance**, the reference width is the palm width (knuckle span), measured between the index finger MCP and the pinky MCP landmarks.

#### Accuracy & Limitations

- Default IPD (63 mm) is an average; individual variation affects accuracy
- Calibration at a known distance significantly improves per-user accuracy
- Accuracy degrades at extreme distances (< 20 cm or > 150 cm)
- Head rotation reduces apparent IPD, causing overestimated distance
- Typical accuracy after calibration: **±5–10 %** in the 30–100 cm range

### Angle Calculation

Joint angles are computed using the **vector dot-product formula**:

```
θ = arccos( (BA · BC) / (|BA| × |BC|) )
```

Where `BA` and `BC` are vectors from the vertex `B` to the two neighbouring joints `A` and `C`.

- A **straight (extended)** finger joint yields angles near **180°**
- A **fully bent** joint yields angles around **60–90°**
- Angles are always returned in **degrees** in the range **[0°, 180°]**

### Motion Tracking

| Metric | Formula | Units |
|---|---|---|
| Velocity | `v = ‖P₂ − P₁‖ / Δt` | pixels/s |
| Direction | `θ = atan2(Δy, Δx)` | degrees |
| Acceleration | `a = (v₂ − v₁) / Δt` | pixels/s² |

**Coordinate system**: Image coordinates where (0, 0) is the top-left corner, x increases rightward, and y increases downward. Angles follow the `atan2` convention: 0° = right, 90° = down, ±180° = left.

### Temporal Filtering

Raw landmark positions are noisy. SpaceSense supports three filter types:

| Filter | Best For | Key Parameter |
|---|---|---|
| **EMA** | Simple smoothing | `α` (0 = max smooth, 1 = no smooth) |
| **One Euro** | Adaptive jitter reduction | `min_cutoff`, `β` |
| **Kalman** | Predictive tracking | Process/measurement noise covariance |

---

## Calibration Guide

### 1. Camera Intrinsic Calibration (Optional)

Use a checkerboard pattern to compute precise camera intrinsics (focal length, distortion coefficients):

1. Print a checkerboard pattern (e.g., 9×6 inner corners)
2. Navigate to **Settings → Camera Calibration**
3. Hold the checkerboard in front of the camera at various angles
4. Capture 10–20 images covering different positions
5. Click **Calibrate** — the system computes and saves intrinsics

### 2. Reference Distance Calibration (Recommended)

Calibrate at a known distance for best accuracy:

1. Measure and mark a known distance from your camera (e.g., 60 cm)
2. Sit at that distance, facing the camera directly
3. Navigate to **Settings → Distance Calibration**
4. Enter the reference distance and click **Calibrate**
5. The system adjusts the focal-length estimate to match

### 3. Threshold Configuration

Adjust ergonomic thresholds in **Settings** or in `.env`:

| Parameter | Default | Description |
|---|---|---|
| `DISTANCE_COMFORTABLE_MIN` | 50 cm | Lower bound of comfortable range |
| `DISTANCE_COMFORTABLE_MAX` | 70 cm | Upper bound of comfortable range |
| `DISTANCE_WARNING` | 50 cm | Trigger WARNING below this distance |
| `DISTANCE_CRITICAL` | 35 cm | Trigger CRITICAL below this distance |

---

## Limitations

> [!IMPORTANT]
> All distance measurements are **estimates** based on geometric models and should not be used for safety-critical applications.

- **Monocular depth**: A single camera cannot provide true depth without calibration assumptions
- **Calibration dependency**: Distance accuracy is only as good as the calibration quality
- **Head rotation**: Turning the head reduces apparent inter-pupillary distance, overestimating distance
- **Lighting**: Low light, backlighting, or extreme contrast degrade landmark detection reliability
- **Occlusion**: Partially occluded faces or hands produce incomplete/noisy landmarks
- **Hardware variance**: Performance depends on CPU/GPU, camera resolution, and USB bandwidth
- **Frame rate**: Processing speed varies; high-resolution cameras may require downscaling

---

## Testing

### Run All Tests

```bash
# Activate your virtual environment first
python -m pytest backend/tests/ -v --tb=short
```

### Run Specific Test File

```bash
python -m pytest backend/tests/test_geometry.py -v
python -m pytest backend/tests/test_distance.py -v
python -m pytest backend/tests/test_filters.py -v
```

### Run Tests Matching a Pattern

```bash
python -m pytest backend/tests/ -v -k "angle"
```

### Windows Script

```powershell
.\scripts\run_tests.ps1
.\scripts\run_tests.ps1 -Filter "distance"
.\scripts\run_tests.ps1 -Verbose
```

### Test Structure

| File | Covers |
|---|---|
| `test_geometry.py` | 3-point angles, movement angles, hand orientation |
| `test_distance.py` | Pinhole distance formula, closest-object selection |
| `test_angles.py` | Finger joint angles (straight, bent, curled, missing) |
| `test_evaluation.py` | MAE, RMSE, relative error, tracking jitter |
| `test_filters.py` | EMA, One Euro, Kalman filter properties |
| `test_ergonomic.py` | State machine, hysteresis, cooldown, time tracking |
| `test_motion.py` | Velocity, direction, acceleration calculations |

---

## Project Structure

```
SpaceSenseAI/
├── backend/
│   ├── analysis/           # Evaluation metrics, data export
│   ├── api/                # FastAPI routes, WebSocket handlers
│   ├── camera/             # Camera capture, calibration
│   ├── database/           # SQLite models, async queries
│   ├── geometry/           # Angle calculator, distance estimator
│   ├── tests/              # pytest test suite
│   │   ├── __init__.py
│   │   ├── test_angles.py
│   │   ├── test_distance.py
│   │   ├── test_ergonomic.py
│   │   ├── test_evaluation.py
│   │   ├── test_filters.py
│   │   ├── test_geometry.py
│   │   └── test_motion.py
│   ├── tracking/           # Temporal filters, motion analyser
│   └── vision/             # MediaPipe face/hand processors
├── calibration/            # User-specific calibration files (.json)
├── data/                   # SQLite database, CSV exports
├── frontend/
│   ├── public/
│   └── src/
│       ├── components/     # Reusable React components
│       ├── hooks/          # Custom React hooks
│       ├── pages/          # Dashboard pages
│       ├── services/       # WebSocket & API clients
│       └── types/          # TypeScript type definitions
├── models/                 # ML model files (.tflite)
├── scripts/
│   ├── start.ps1           # PowerShell start script
│   ├── start.bat           # Batch start script
│   └── run_tests.ps1       # Test runner script
├── .env.example            # Environment variable template
├── .gitignore
├── README.md
└── requirements.txt
```

---

## API Documentation

Start the backend and visit:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Privacy

SpaceSense AI is designed with privacy as a core principle:

- ✅ **All processing happens locally** on your machine
- ✅ **No video data is uploaded** — frames are processed in-memory and discarded
- ✅ **No telemetry or analytics** — zero external network calls
- ✅ **Only session metrics are stored** (distances, angles, timestamps) — never images
- ✅ **Data is fully deletable** — delete `data/` directory or use the UI

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Write tests for new functionality
4. Run the test suite: `python -m pytest backend/tests/ -v`
5. Submit a pull request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

*Your Name — [your.email@example.com](mailto:your.email@example.com)*

---

<p align="center">
  Built with ❤️ using OpenCV, MediaPipe, FastAPI & React
</p>

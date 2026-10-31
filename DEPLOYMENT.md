# Deployment & Live Hosting Guide — SpaceSense AI

This guide explains how to deploy **SpaceSense AI** to 24/7 free-tier cloud platforms (Vercel + Render or Railway) so interviewers, mentors, and recruiters can test your application online directly from their browsers.

---

## Architecture Overview

```
[ User Browser (Interviewer/Mentor) ]
       │                │
  HTTP │                │ WebSockets (Real-time tracking stream)
       ▼                ▼
 [ Vercel / Netlify ]  [ Render / Railway ]
 React + Vite Frontend   Dockerized Python FastAPI Backend
                         ├── MediaPipe (Hand & Face landmarkers)
                         ├── OpenCV Preprocessing
                         ├── Geometric Engine & Biomechanics
                         └── SQLite Session Persistence
```

---

## 1. Push Your Code to GitHub

Open PowerShell or Command Prompt in `D:\projects\SpaceSenseAI`:

```bash
git init
git add .
git commit -m "feat: complete SpaceSense AI with cloud deployment setup"
git branch -M main
git remote add origin https://github.com/<your-username>/SpaceSenseAI.git
git push -u origin main
```

*(The included `.github/workflows/ci.yml` will automatically trigger and run your 150 unit tests on GitHub Actions.)*

---

## 2. Deploy the CV Backend on Render (Free Tier)

1. Go to [Render Dashboard](https://dashboard.render.com/) and sign up with GitHub.
2. Click **New +** $\to$ **Web Service**.
3. Select your `SpaceSenseAI` repository.
4. Configure the service:
   - **Name**: `spacesense-backend`
   - **Language / Runtime**: `Docker` *(Render will automatically detect your root `Dockerfile`)*
   - **Region**: Choose the closest region (e.g., Oregon or Frankfurt)
   - **Branch**: `main`
   - **Instance Type**: `Free`
5. Click **Create Web Service**.
6. Once deployed (takes 2–3 minutes to build the container), Render gives you a secure HTTPS URL:
   `https://spacesense-backend.onrender.com`

---

## 3. Deploy the Frontend on Vercel (Free Tier)

1. Go to [Vercel](https://vercel.com/) and sign in with GitHub.
2. Click **Add New...** $\to$ **Project**.
3. Select the `SpaceSenseAI` repository.
4. In the Project Configuration:
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click edit and select `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
5. Expand **Environment Variables** and add:
   - `VITE_API_BASE`: `https://spacesense-backend.onrender.com`
   - `VITE_WS_BASE`: `wss://spacesense-backend.onrender.com`
6. Click **Deploy**.
7. In ~1 minute, your live URL will be active:
   `https://spacesense-ai.vercel.app` (or your custom domain).

---

## 4. Alternative: Single-Command Local/Cloud Docker Deployment

If running on any virtual private server (DigitalOcean droplet, AWS EC2, or local machine):

```bash
docker compose up --build
```
- Frontend will be live on `http://localhost:3000`
- Backend will be live on `http://localhost:8000`

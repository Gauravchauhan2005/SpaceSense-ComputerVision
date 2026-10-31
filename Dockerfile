# ==============================================================================
# SpaceSense AI — Production Dockerfile
# ==============================================================================
FROM python:3.11-slim

# Prevent Python from writing .pyc files & buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Install Debian packages required by OpenCV, MediaPipe, and camera/graphics backends
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend, models, and create data/calibration directories
COPY backend/ ./backend/
COPY models/ ./models/
RUN mkdir -p data calibration

EXPOSE 8000

# Healthcheck for container orchestration (Render, Railway, Fly.io, AWS)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:${PORT}/api/health || exit 1

# Start FastAPI application
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]

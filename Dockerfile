# ============================================================
# JURICOB - Single container: FastAPI serves API + React SPA
# Coolify: Build Pack=Dockerfile, Ports Exposes=8000
# NO NGINX NEEDED - FastAPI handles everything
# ============================================================

# Stage 1: Build React frontend
FROM node:18-alpine AS build_frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python + FastAPI only
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# aiofiles is required for FastAPI StaticFiles
RUN pip install --no-cache-dir aiofiles

# Copy all backend code
COPY backend/ ./backend/

# Copy built React frontend into /app/dist
COPY --from=build_frontend /app/frontend/dist /app/dist

EXPOSE 8000

# Run FastAPI - it serves BOTH the API (/api/*) AND the React SPA (/)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

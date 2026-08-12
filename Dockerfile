# Single-container Dockerfile: React Frontend + Python FastAPI Backend
# Coolify: Build Pack=Dockerfile, Dockerfile Location=/Dockerfile, Ports Exposes=8000

# Stage 1: Build the React application
FROM node:20-slim AS build_frontend

WORKDIR /app/frontend

# Copiar dependencias del frontend
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps

# Copiar código del frontend y compilar con memoria optimizada
COPY frontend/ ./
ENV NODE_OPTIONS="--max-old-space-size=4096"
RUN npm run build

# Stage 2: Python 3.11 + FastAPI Single Container
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir aiofiles

COPY . .
COPY --from=build_frontend /app/frontend/dist /app/dist

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

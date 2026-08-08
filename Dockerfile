# Single-container Dockerfile: React Frontend + Python FastAPI Backend
# Coolify: Build Pack=Dockerfile, Dockerfile Location=/Dockerfile, Ports Exposes=8000

# Stage 1: Build the React application
FROM node:18-alpine AS build_frontend

WORKDIR /app

COPY package*.json ./
COPY frontend/package*.json ./frontend/

RUN if [ -f "frontend/package.json" ]; then cd frontend && npm install; else npm install; fi
COPY . ./
RUN if [ -d "frontend" ]; then cd frontend && npm run build; else npm run build; fi

RUN mkdir -p /app/dist && \
    if [ -d "frontend/dist" ]; then cp -a frontend/dist/. /app/dist/ ; \
    elif [ -d "dist" ]; then cp -a dist/. /app/dist/ ; fi

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
COPY --from=build_frontend /app/dist /app/dist

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

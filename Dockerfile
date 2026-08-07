# Stage 1: Build the React frontend application
FROM node:18-alpine AS build_frontend

WORKDIR /app

# Copy package manifests
COPY package*.json ./
COPY frontend/package*.json ./frontend/

# Install Node dependencies and build
RUN cd frontend && npm install

COPY . ./

RUN cd frontend && npm run build

# Stage 2: Combined Python 3.11 FastAPI + Nginx Container
FROM python:3.11-slim

# Install system dependencies including Nginx and libpq for PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend dependencies and install
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy all application code
COPY . .

# Copy built React assets into Nginx html directory
COPY --from=build_frontend /app/frontend/dist /usr/share/nginx/html

# Copy Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Create startup script to run FastAPI backend (port 8000) and Nginx frontend (port 80)
RUN echo '#!/bin/sh' > /app/start.sh && \
    echo 'echo "Iniciando Backend Uvicorn (FastAPI) en 127.0.0.1:8000..."' >> /app/start.sh && \
    echo 'uvicorn backend.main:app --host 127.0.0.1 --port 8000 &' >> /app/start.sh && \
    echo 'sleep 2' >> /app/start.sh && \
    echo 'echo "Iniciando Servidor Web Nginx en puerto 80..."' >> /app/start.sh && \
    echo 'nginx -g "daemon off;"' >> /app/start.sh && \
    chmod +x /app/start.sh

EXPOSE 80

CMD ["/app/start.sh"]

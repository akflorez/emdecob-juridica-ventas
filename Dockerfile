# Single-container Dockerfile: React Frontend + Python FastAPI Backend
# Coolify must use Build Pack: Dockerfile with this file

# ============================================
# Stage 1: Build the React frontend
# ============================================
FROM node:18-alpine AS build_frontend

WORKDIR /app/frontend

# Copy only the frontend package files first for better Docker cache
COPY frontend/package*.json ./

# Install dependencies
RUN npm install

# Copy frontend source code
COPY frontend/ ./

# Build the React app
RUN npm run build

# ============================================
# Stage 2: Python 3.11 + Nginx combined
# ============================================
FROM python:3.11-slim

# Install Nginx + PostgreSQL client + build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    libpq-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python backend dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full application code
COPY . .

# Copy built React assets into /app/dist (Nginx will serve from here)
COPY --from=build_frontend /app/frontend/dist /app/dist

# ============================================
# Nginx Configuration (inline, no external file needed)
# ============================================
RUN rm -f /etc/nginx/sites-enabled/default && \
    cat > /etc/nginx/sites-enabled/juricob.conf << 'NGINXEOF'
server {
    listen 80 default_server;
    server_name _;

    root /app/dist;
    index index.html;

    # Disable caching of index.html
    location = /index.html {
        add_header Cache-Control "no-store, no-cache, must-revalidate";
    }

    # Proxy /api/* -> FastAPI (strips /api prefix)
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
    }

    # Proxy /auth/* -> FastAPI directly
    location /auth/ {
        proxy_pass http://127.0.0.1:8000/auth/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
    }

    # Static assets with long cache
    location /assets/ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # SPA fallback - always return index.html for client-side routing
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINXEOF

# ============================================
# Startup script: Launch FastAPI then Nginx
# ============================================
RUN cat > /app/start.sh << 'STARTEOF'
#!/bin/sh
set -e

echo "[STARTUP] Starting FastAPI backend on 127.0.0.1:8000..."
cd /app
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 &
BACKEND_PID=$!

echo "[STARTUP] Waiting 3 seconds for backend to initialize..."
sleep 3

echo "[STARTUP] Verifying backend is up..."
for i in 1 2 3 4 5; do
    if curl -s http://127.0.0.1:8000/docs > /dev/null 2>&1; then
        echo "[STARTUP] Backend is ready!"
        break
    fi
    echo "[STARTUP] Waiting... attempt $i"
    sleep 2
done

echo "[STARTUP] Starting Nginx on port 80..."
nginx -t && nginx -g "daemon off;"
STARTEOF

RUN chmod +x /app/start.sh

EXPOSE 80

CMD ["/app/start.sh"]

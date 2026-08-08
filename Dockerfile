# Single-container Dockerfile: React Frontend + Python FastAPI Backend
# Coolify: Build Pack=Dockerfile, Dockerfile Location=/Dockerfile, Ports Exposes=80

# ============================================
# Stage 1: Build the React frontend
# ============================================
FROM node:18-alpine AS build_frontend

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ============================================
# Stage 2: Python 3.11 + Nginx combined
# ============================================
FROM python:3.11-slim

# Install system deps: Nginx + wget (for health check) + build libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    wget \
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

# Copy built React assets
COPY --from=build_frontend /app/frontend/dist /app/dist

# ============================================
# Copy Nginx config (file already in repo - no heredoc issues)
# ============================================
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default \
    && rm -f /etc/nginx/conf.d/*
COPY nginx.conf /etc/nginx/sites-available/juricob
RUN ln -s /etc/nginx/sites-available/juricob /etc/nginx/sites-enabled/juricob

# ============================================
# Copy startup script (file already in repo - no heredoc issues)
# ============================================
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 80

CMD ["/app/start.sh"]

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

# Install system deps: Nginx + wget + build libs
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
# Nginx Config - written with printf to guarantee LF, no BOM
# ============================================
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/sites-available/default \
    && rm -f /etc/nginx/conf.d/*

RUN printf 'server {\n\
    listen 80 default_server;\n\
    server_name _;\n\
    root /app/dist;\n\
    index index.html;\n\
    location /api/ {\n\
        proxy_pass http://127.0.0.1:8000/;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n\
        proxy_set_header X-Forwarded-Proto $scheme;\n\
        proxy_connect_timeout 60s;\n\
        proxy_read_timeout 120s;\n\
    }\n\
    location /auth/ {\n\
        proxy_pass http://127.0.0.1:8000/auth/;\n\
        proxy_http_version 1.1;\n\
        proxy_set_header Host $host;\n\
        proxy_set_header X-Real-IP $remote_addr;\n\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n\
        proxy_set_header X-Forwarded-Proto $scheme;\n\
        proxy_connect_timeout 60s;\n\
        proxy_read_timeout 120s;\n\
    }\n\
    location /assets/ {\n\
        expires 1y;\n\
        add_header Cache-Control "public, immutable";\n\
    }\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/sites-available/juricob \
    && ln -s /etc/nginx/sites-available/juricob /etc/nginx/sites-enabled/juricob

# Validate Nginx config at build time
RUN nginx -t

# ============================================
# CMD inline - no external script file, no encoding issues
# ============================================
CMD sh -c 'cd /app && uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 & sleep 8 && nginx -g "daemon off;"'

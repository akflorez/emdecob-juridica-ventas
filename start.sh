#!/bin/sh
set -e

echo "[STARTUP] Starting FastAPI backend on 127.0.0.1:8000..."
cd /app
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1 &
BACKEND_PID=$!

echo "[STARTUP] Waiting 5 seconds for backend to initialize..."
sleep 5

echo "[STARTUP] Verifying backend is up with wget..."
for i in 1 2 3 4 5 6 7 8 9 10; do
    if wget -q -O /dev/null http://127.0.0.1:8000/docs 2>/dev/null; then
        echo "[STARTUP] Backend is ready! (attempt $i)"
        break
    fi
    echo "[STARTUP] Backend not ready yet, attempt $i/10, waiting 3s..."
    sleep 3
done

echo "[STARTUP] Starting Nginx on port 80..."
nginx -t && nginx -g "daemon off;"

#!/usr/bin/env bash
set -euo pipefail

# Ensure we can find Python console scripts installed into the image venv.
# NOTE: Kamal runs `bash -lc ...` which can reset PATH; this makes it explicit.
export PATH="/opt/venv/bin:$PATH"

echo "[start_web_singlehost] starting FastAPI (uvicorn) on 127.0.0.1:8001"
cd /app/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --ws websockets &
UVICORN_PID=$!

echo "[start_web_singlehost] starting SSR (react-router-serve) on 0.0.0.0:3000"
cd /app/frontend
export NODE_ENV="${NODE_ENV:-production}"
export PORT="${PORT:-3000}"

# Prefer loopback through nginx for consistency with the browser's path-based API URL.
export API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000/api/v1}"

npm start &
SSR_PID=$!

cleanup() {
  echo "[start_web_singlehost] shutting down..."
  kill "$SSR_PID" "$UVICORN_PID" 2>/dev/null || true
  wait "$SSR_PID" "$UVICORN_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[start_web_singlehost] starting nginx (public) on 0.0.0.0:8000"
exec nginx -g 'daemon off;'

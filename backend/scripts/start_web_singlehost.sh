#!/usr/bin/env bash
set -euo pipefail

# Ensure we can find Python console scripts installed into the image venv.
# NOTE: Kamal runs `bash -lc ...` which can reset PATH; this makes it explicit.
export PATH="/opt/venv/bin:$PATH"

export WEB_UVICORN_WORKERS="${WEB_UVICORN_WORKERS:-2}"

echo "[start_web_singlehost] starting FastAPI (uvicorn) on 127.0.0.1:8001 with ${WEB_UVICORN_WORKERS} workers"
cd /app/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --ws websockets --workers "${WEB_UVICORN_WORKERS}" &
UVICORN_PID=$!

echo "[start_web_singlehost] starting SSR (react-router-serve) on 0.0.0.0:3000"
cd /app/frontend
export NODE_ENV="${NODE_ENV:-production}"
export PORT="${PORT:-3000}"

# Let SSR talk directly to FastAPI on loopback so loader/action fetches avoid
# an extra nginx hop inside the same container.
export API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8001/api/v1}"

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

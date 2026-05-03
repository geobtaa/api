#!/usr/bin/env bash
set -euo pipefail

# Ensure we can find Python console scripts installed into the image venv.
# NOTE: Kamal runs `bash -lc ...` which can reset PATH; this makes it explicit.
export PATH="/opt/venv/bin:$PATH"

export WEB_UVICORN_WORKERS="${WEB_UVICORN_WORKERS:-2}"
export WEB_INTERNAL_UVICORN_WORKERS="${WEB_INTERNAL_UVICORN_WORKERS:-1}"

# Kamal's bridged asset directory can arrive owned by a transient numeric UID
# with restrictive permissions. Normalize it before nginx serves /assets/.
if [ -d /app/frontend/build/client/assets ]; then
  chmod -R a+rX /app/frontend/build/client/assets || true
fi

echo "[start_web_singlehost] starting public FastAPI (uvicorn) on 127.0.0.1:8001 with ${WEB_UVICORN_WORKERS} workers"
cd /app/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --ws websockets --workers "${WEB_UVICORN_WORKERS}" &
PUBLIC_UVICORN_PID=$!

INTERNAL_UVICORN_PID=""
if [ "${WEB_INTERNAL_UVICORN_WORKERS}" != "0" ]; then
  echo "[start_web_singlehost] starting internal FastAPI (uvicorn) on 127.0.0.1:8002 with ${WEB_INTERNAL_UVICORN_WORKERS} workers"
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --ws websockets --workers "${WEB_INTERNAL_UVICORN_WORKERS}" &
  INTERNAL_UVICORN_PID=$!
fi

echo "[start_web_singlehost] starting SSR (react-router-serve) on 0.0.0.0:3000"
cd /app/frontend
export NODE_ENV="${NODE_ENV:-production}"
export PORT="${PORT:-3000}"

# Let SSR talk directly to FastAPI on loopback so loader/action fetches avoid
# an extra nginx hop inside the same container. By default SSR uses its own
# internal FastAPI pool so browser-facing BFF calls cannot occupy the public
# /api worker queue used by QGIS, MCP, and external API clients.
if [ -z "${API_BASE_URL:-}" ]; then
  if [ "${WEB_INTERNAL_UVICORN_WORKERS}" != "0" ]; then
    export API_BASE_URL="http://127.0.0.1:8002/api/v1"
  else
    export API_BASE_URL="http://127.0.0.1:8001/api/v1"
  fi
fi

npm start &
SSR_PID=$!

cleanup() {
  echo "[start_web_singlehost] shutting down..."
  if [ -n "$INTERNAL_UVICORN_PID" ]; then
    kill "$SSR_PID" "$PUBLIC_UVICORN_PID" "$INTERNAL_UVICORN_PID" 2>/dev/null || true
    wait "$SSR_PID" "$PUBLIC_UVICORN_PID" "$INTERNAL_UVICORN_PID" 2>/dev/null || true
  else
    kill "$SSR_PID" "$PUBLIC_UVICORN_PID" 2>/dev/null || true
    wait "$SSR_PID" "$PUBLIC_UVICORN_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "[start_web_singlehost] starting nginx (public) on 0.0.0.0:8000"
exec nginx -g 'daemon off;'

#!/usr/bin/env bash
set -euo pipefail

# Ensure we can find Python console scripts installed into the image venv.
# NOTE: Kamal runs `bash -lc ...` which can reset PATH; this makes it explicit.
export PATH="/opt/venv/bin:$PATH"

export WEB_UVICORN_WORKERS="${WEB_UVICORN_WORKERS:-2}"
export WEB_INTERNAL_UVICORN_WORKERS="${WEB_INTERNAL_UVICORN_WORKERS:-1}"
export WEB_SSR_WORKERS="${WEB_SSR_WORKERS:-1}"

if ! [[ "${WEB_SSR_WORKERS}" =~ ^[1-9][0-9]*$ ]]; then
  echo "[start_web_singlehost] WEB_SSR_WORKERS must be a positive integer, got ${WEB_SSR_WORKERS}" >&2
  exit 1
fi

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

echo "[start_web_singlehost] configuring nginx SSR upstream for ${WEB_SSR_WORKERS} worker(s)"
{
  echo "upstream ssr_backend {"
  echo "    least_conn;"
  echo "    keepalive 32;"
  for ((i = 0; i < WEB_SSR_WORKERS; i++)); do
    echo "    server 127.0.0.1:$((3000 + i));"
  done
  echo "}"
} > /etc/nginx/ssr-upstream.conf

echo "[start_web_singlehost] starting ${WEB_SSR_WORKERS} SSR worker(s) (react-router-serve)"
cd /app/frontend
export NODE_ENV="${NODE_ENV:-production}"

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

SSR_PIDS=()
for ((i = 0; i < WEB_SSR_WORKERS; i++)); do
  SSR_PORT=$((3000 + i))
  echo "[start_web_singlehost] starting SSR worker on 0.0.0.0:${SSR_PORT}"
  PORT="${SSR_PORT}" npm start &
  SSR_PIDS+=("$!")
done

cleanup() {
  echo "[start_web_singlehost] shutting down..."
  PIDS=("${SSR_PIDS[@]}" "$PUBLIC_UVICORN_PID")
  if [ -n "$INTERNAL_UVICORN_PID" ]; then
    PIDS+=("$INTERNAL_UVICORN_PID")
  fi
  kill "${PIDS[@]}" 2>/dev/null || true
  wait "${PIDS[@]}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "[start_web_singlehost] starting nginx (public) on 0.0.0.0:8000"
exec nginx -g 'daemon off;'

#!/bin/sh
# Only the dedicated integration database is managed by this helper.
set -eu
cd "$(dirname "$0")/.."
if [ -z "${TEST_DATABASE_URL:-}" ]; then
  docker compose -f compose.test.yaml up -d --wait
  TEST_DATABASE_URL="postgresql+asyncpg://geomg_test:geomg_test@127.0.0.1:${TEST_POSTGRES_PORT:-25432}/geomg_test"
  export TEST_DATABASE_URL
fi
cd backend
exec uv run pytest "$@"

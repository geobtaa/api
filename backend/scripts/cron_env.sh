#!/usr/bin/env bash

set -a

CRON_ENV_OUTPUT_PATH="${CRON_ENV_OUTPUT_PATH:-/tmp/cron-container-env.sh}"

if [ -r "$CRON_ENV_OUTPUT_PATH" ]; then
  # shellcheck disable=SC1090
  . "$CRON_ENV_OUTPUT_PATH"
fi

export TZ="${TZ:-America/Chicago}"
export BRIDGE_SYNC_LOCAL_TIMEZONE="${BRIDGE_SYNC_LOCAL_TIMEZONE:-$TZ}"

set +a

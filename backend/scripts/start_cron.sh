#!/usr/bin/env bash
set -euo pipefail

CRON_LOCAL_TIMEZONE="${BRIDGE_SYNC_LOCAL_TIMEZONE:-America/Chicago}"
ZONEINFO_PATH="/usr/share/zoneinfo/${CRON_LOCAL_TIMEZONE}"

if [ -f "${ZONEINFO_PATH}" ]; then
  ln -snf "${ZONEINFO_PATH}" /etc/localtime
  echo "${CRON_LOCAL_TIMEZONE}" > /etc/timezone
  export TZ="${CRON_LOCAL_TIMEZONE}"
else
  echo "ERROR: timezone ${CRON_LOCAL_TIMEZONE} not found; refusing to start cron with the container default timezone" >&2
  exit 1
fi

export BRIDGE_SYNC_LOCAL_TIMEZONE="${BRIDGE_SYNC_LOCAL_TIMEZONE:-${CRON_LOCAL_TIMEZONE}}"

/opt/venv/bin/python3 /app/scripts/render_cron_env.py /tmp/cron-container-env.sh

{
  printf "ADMIN_USERNAME=%s\n" "${ADMIN_USERNAME}"
  printf "ADMIN_PASSWORD=%s\n" "${ADMIN_PASSWORD}"
  printf "APPLICATION_URL=%s\n" "${APPLICATION_URL}"
  printf "BRIDGE_TRIGGER=%s\n" "${BRIDGE_TRIGGER:-nightly_cron}"
  cat /app/config/crontab
} | crontab -

exec cron -f

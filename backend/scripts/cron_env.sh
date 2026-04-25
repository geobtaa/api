#!/usr/bin/env bash

set -a

while IFS= read -r line; do
  case "$line" in
    ADMIN_*|APP_*|APPLICATION_URL=*|BRIDGE_*|CACHE_*|CELERY_*|CORS_*|DATABASE_URL=*|ELASTICSEARCH_*|ENDPOINT_CACHE=*|IS_DOCKER=*|KAMAL_DEST=*|KITHE_BRIDGE_*|LOG_*|OPENAI_*|POSTGRES_*|PYTHONPATH=*|RATE_LIMIT_*|REDIS_*|SEARCH_ENGINE_*|SENDMAIL_*|SMTP_*|STATIC_MAPS_DIR=*|THUMBNAIL_*|WEB_*)
      export "$line"
      ;;
  esac
done < <(tr '\0' '\n' </proc/1/environ)

export TZ="${TZ:-America/Chicago}"
export BRIDGE_SYNC_LOCAL_TIMEZONE="${BRIDGE_SYNC_LOCAL_TIMEZONE:-$TZ}"

set +a

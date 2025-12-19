#!/bin/sh
set -e

# Use envsubst to substitute environment variables in nginx config template
# This allows us to inject the API key from environment variables
# If envsubst is not available, install gettext (which includes envsubst)
if ! command -v envsubst >/dev/null 2>&1; then
    echo "envsubst not found, installing gettext..."
    apk add --no-cache gettext
fi

# Substitute environment variables in the template
envsubst '${BTAA_GEOSPATIAL_API_KEY}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

# Start nginx
exec nginx -g 'daemon off;'


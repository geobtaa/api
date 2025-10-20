#!/bin/bash
# Clone btaa_ogm_api database to btaa_ogm_api_test for testing

set -e

echo "Cloning btaa_ogm_api to btaa_ogm_api_test..."

# Drop test DB if it exists
docker compose exec -T paradedb bash -lc 'PGPASSWORD=$POSTGRES_PASSWORD psql -U postgres -c "DROP DATABASE IF EXISTS btaa_ogm_api_test;"'

# Create test DB as a clone
docker compose exec -T paradedb bash -lc 'PGPASSWORD=$POSTGRES_PASSWORD psql -U postgres -c "CREATE DATABASE btaa_ogm_api_test WITH TEMPLATE btaa_ogm_api OWNER postgres;"'

echo "✓ Database cloned successfully!"
echo ""
echo "To verify:"
echo "  docker compose exec -T paradedb psql -U postgres -d btaa_ogm_api_test -c 'SELECT COUNT(*) FROM resources;'"


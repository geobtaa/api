#!/bin/bash

# Script to run tests with real data piggy-backing on primary services

echo "Setting up test environment..."

# Set environment variables targeting primary services with isolated DB/index
export DB_USER="${DB_USER:-postgres}"
export DB_PASSWORD="${DB_PASSWORD:-postgres}"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT="${DB_PORT:-2345}"
export TEST_DB_NAME="${TEST_DB_NAME:-btaa_ogm_api_test}"
export DATABASE_URL="postgresql+asyncpg://$DB_USER:$DB_PASSWORD@$DB_HOST:$DB_PORT/$TEST_DB_NAME"

export ELASTICSEARCH_URL="${ELASTICSEARCH_URL:-http://localhost:9200}"
export ELASTICSEARCH_INDEX="${ELASTICSEARCH_INDEX:-btaa_ogm_api_test}"

export REDIS_HOST="${REDIS_HOST:-localhost}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export REDIS_DB="${REDIS_DB:-1}"

echo "Test environment variables set:"
echo "DATABASE_URL: $DATABASE_URL"
echo "ELASTICSEARCH_URL: $ELASTICSEARCH_URL"
echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PORT: $REDIS_PORT"
echo "ELASTICSEARCH_INDEX: $ELASTICSEARCH_INDEX"

echo ""
echo "Waiting for services to be ready..."

# Wait for database to be ready (primary ParadeDB)
echo "Waiting for database..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; do
    echo "Database not ready, waiting..."
    sleep 2
done
echo "Database is ready!"

# Wait for Elasticsearch to be ready (primary ES)
echo "Waiting for Elasticsearch..."
until curl -s "$ELASTICSEARCH_URL/_cluster/health" > /dev/null 2>&1; do
    echo "Elasticsearch not ready, waiting..."
    sleep 2
done
echo "Elasticsearch is ready!"

# Wait for Redis to be ready (primary Redis)
echo "Waiting for Redis..."
until redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping > /dev/null 2>&1; do
    echo "Redis not ready, waiting..."
    sleep 2
done
echo "Redis is ready!"

echo ""
echo "All services are ready! Running tests..."

# Run the tests
python -m pytest "$@"

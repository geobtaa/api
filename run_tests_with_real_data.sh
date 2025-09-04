#!/bin/bash

# Script to run tests with real data using test environment services

echo "Setting up test environment..."

# Set environment variables for test services
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:2346/btaa_ogm_api_test"
export ELASTICSEARCH_URL="http://localhost:9201"
export REDIS_HOST="localhost"
export REDIS_PORT="6380"
export ELASTICSEARCH_INDEX="btaa_ogm_api_test"

echo "Test environment variables set:"
echo "DATABASE_URL: $DATABASE_URL"
echo "ELASTICSEARCH_URL: $ELASTICSEARCH_URL"
echo "REDIS_HOST: $REDIS_HOST"
echo "REDIS_PORT: $REDIS_PORT"
echo "ELASTICSEARCH_INDEX: $ELASTICSEARCH_INDEX"

echo ""
echo "Waiting for services to be ready..."

# Wait for database to be ready
echo "Waiting for database..."
until docker exec btaa-ogm-api-paradedb-test pg_isready -U postgres > /dev/null 2>&1; do
    echo "Database not ready, waiting..."
    sleep 2
done
echo "Database is ready!"

# Wait for Elasticsearch to be ready
echo "Waiting for Elasticsearch..."
until curl -s http://localhost:9201/_cluster/health > /dev/null 2>&1; do
    echo "Elasticsearch not ready, waiting..."
    sleep 2
done
echo "Elasticsearch is ready!"

# Wait for Redis to be ready
echo "Waiting for Redis..."
until docker exec btaa-ogm-api-redis-test redis-cli ping > /dev/null 2>&1; do
    echo "Redis not ready, waiting..."
    sleep 2
done
echo "Redis is ready!"

echo ""
echo "All services are ready! Running tests..."

# Run the tests
python -m pytest "$@"

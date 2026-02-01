.PHONY: lint lint-check format test lint-test test-coverage-compare db-export db-import db-sync reindex verify-h3-index clear_cache frontend-reset

# Load environment variables from .env file if it exists
-include .env
export

# Load Kamal configuration if it exists
ifneq (,$(wildcard .kamal/secrets))
    include .kamal/secrets
endif

# Coverage threshold - tests will fail if coverage drops below this percentage
# Can be overridden with: COVERAGE_THRESHOLD=25 make test
COVERAGE_THRESHOLD ?= 50

# Number of parallel workers for pytest-xdist
# Default: 4 (to avoid hitting PostgreSQL connection limits)
# Can be overridden with: PARALLEL_WORKERS=8 make test
# Use 'auto' to use all CPU cores (may hit connection limits with many cores)
# Set to 0 or empty to disable parallelism
PARALLEL_WORKERS ?= 4

# Hard stop for a "hung" test run (seconds). 0 disables.
# CI expectation: the *entire* suite should return quickly; keep this tight by default.
# Override examples:
#   - WALLCLOCK_TIMEOUT_SECONDS=0 make test        # no timeout (debug only)
#   - WALLCLOCK_TIMEOUT_SECONDS=900 make test      # 15 minutes
WALLCLOCK_TIMEOUT_SECONDS ?= 60

# On timeout, we send SIGINT first so pytest can print its normal summary.
# If it doesn't exit within the grace period, we escalate to SIGTERM/SIGKILL.
TIMEOUT_GRACE_SECONDS ?= 20

# Default: don't print giant stack dumps on timeout (keeps output readable).
# Enable only when debugging a true deadlock/hang:
#   TIMEOUT_DUMP_STACKS=1 make test-no-coverage
TIMEOUT_DUMP_STACKS ?= 0

# Run both linting and formatting checks (without modifying files)
lint:
	@echo "Checking code with ruff..."
	ruff check backend/app/ backend/tests/ backend/scripts/

# Format code in-place
format:
	@echo "Formatting code with ruff..."
	ruff format backend/app/ backend/tests/ backend/scripts/
	ruff check --fix backend/app/ backend/tests/ backend/scripts/

# Check formatting only (for CI)
lint-check:
	@echo "Checking formatting with ruff..."
	ruff format --check backend/app/ backend/tests/ backend/scripts/
	ruff check backend/app/ backend/tests/ backend/scripts/

# Run just the tests with coverage threshold
test:
	@echo "Setting up test database..."
	@echo "Checking if test database exists..."
	@if docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -lqt | cut -d \| -f 1 | grep -qw btaa_geospatial_api_test'; then \
		echo "Test database already exists, skipping clone..."; \
	else \
		echo "Test database does not exist, cloning from production..."; \
		docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '"'"'btaa_geospatial_api'"'"' AND pid <> pg_backend_pid();"' || true; \
		docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -c "CREATE DATABASE btaa_geospatial_api_test WITH TEMPLATE btaa_geospatial_api OWNER postgres;"'; \
	fi
	@echo "Running tests with coverage threshold of $(COVERAGE_THRESHOLD)%..."
	@if [ -n "$(PARALLEL_WORKERS)" ] && [ "$(PARALLEL_WORKERS)" != "0" ]; then \
		echo "Running tests in parallel with $(PARALLEL_WORKERS) workers..."; \
		cd backend && \
		WALLCLOCK_TIMEOUT_SECONDS="$(WALLCLOCK_TIMEOUT_SECONDS)" TIMEOUT_GRACE_SECONDS="$(TIMEOUT_GRACE_SECONDS)" TIMEOUT_DUMP_STACKS="$(TIMEOUT_DUMP_STACKS)" \
		python scripts/run_with_timeout.py python -X faulthandler -m pytest -n $(PARALLEL_WORKERS) --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=$(COVERAGE_THRESHOLD); \
	else \
		echo "Running tests sequentially..."; \
		cd backend && \
		WALLCLOCK_TIMEOUT_SECONDS="$(WALLCLOCK_TIMEOUT_SECONDS)" TIMEOUT_GRACE_SECONDS="$(TIMEOUT_GRACE_SECONDS)" TIMEOUT_DUMP_STACKS="$(TIMEOUT_DUMP_STACKS)" \
		python scripts/run_with_timeout.py python -X faulthandler -m pytest --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=$(COVERAGE_THRESHOLD); \
	fi

# Run just the tests without coverage threshold (for debugging)
test-no-coverage:
	@echo "Running tests without coverage threshold..."
	@if [ -n "$(PARALLEL_WORKERS)" ] && [ "$(PARALLEL_WORKERS)" != "0" ]; then \
		echo "Running tests in parallel with $(PARALLEL_WORKERS) workers..."; \
		cd backend && \
		WALLCLOCK_TIMEOUT_SECONDS="$(WALLCLOCK_TIMEOUT_SECONDS)" TIMEOUT_GRACE_SECONDS="$(TIMEOUT_GRACE_SECONDS)" TIMEOUT_DUMP_STACKS="$(TIMEOUT_DUMP_STACKS)" \
		python scripts/run_with_timeout.py python -X faulthandler -m pytest -n $(PARALLEL_WORKERS) --full-trace; \
	else \
		cd backend && \
		WALLCLOCK_TIMEOUT_SECONDS="$(WALLCLOCK_TIMEOUT_SECONDS)" TIMEOUT_GRACE_SECONDS="$(TIMEOUT_GRACE_SECONDS)" TIMEOUT_DUMP_STACKS="$(TIMEOUT_DUMP_STACKS)" \
		python scripts/run_with_timeout.py python -X faulthandler -m pytest --full-trace; \
	fi

# Run tests in parallel without coverage (fastest option for local development)
test-fast:
	@echo "Running tests in parallel without coverage (fast mode)..."
	@if [ -n "$(PARALLEL_WORKERS)" ] && [ "$(PARALLEL_WORKERS)" != "0" ]; then \
		cd backend && \
		WALLCLOCK_TIMEOUT_SECONDS="$(WALLCLOCK_TIMEOUT_SECONDS)" TIMEOUT_GRACE_SECONDS="$(TIMEOUT_GRACE_SECONDS)" TIMEOUT_DUMP_STACKS="$(TIMEOUT_DUMP_STACKS)" \
		python scripts/run_with_timeout.py python -X faulthandler -m pytest -n $(PARALLEL_WORKERS); \
	else \
		cd backend && \
		WALLCLOCK_TIMEOUT_SECONDS="$(WALLCLOCK_TIMEOUT_SECONDS)" TIMEOUT_GRACE_SECONDS="$(TIMEOUT_GRACE_SECONDS)" TIMEOUT_DUMP_STACKS="$(TIMEOUT_DUMP_STACKS)" \
		python scripts/run_with_timeout.py python -X faulthandler -m pytest -n 4; \
	fi

# Force a fresh clone of the test database
test-fresh-db:
	@echo "Force cloning fresh test database..."
	@docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '"'"'btaa_geospatial_api'"'"' AND pid <> pg_backend_pid();"' || true
	@docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -c "DROP DATABASE IF EXISTS btaa_geospatial_api_test;"' || true
	@docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -c "CREATE DATABASE btaa_geospatial_api_test WITH TEMPLATE btaa_geospatial_api OWNER postgres;"'
	@echo "Fresh test database created!"

# Run tests and compare coverage against previous run (fails if coverage drops)
test-coverage-compare:
	@echo "Running tests with coverage comparison..."
	@if [ -n "$$BASELINE_COVERAGE" ]; then \
		echo "Baseline coverage: $$BASELINE_COVERAGE%"; \
		cd backend && pytest --cov=app --cov-report=term-missing --cov-report=html --cov-report=xml; \
		CURRENT_COVERAGE=$$(grep -o 'line-rate="[^"]*"' coverage.xml | head -1 | sed 's/line-rate="\([^"]*\)"/\1/' | awk '{printf "%.0f", $$1 * 100}'); \
		echo "Current coverage: $$CURRENT_COVERAGE%"; \
		if [ -n "$$CURRENT_COVERAGE" ]; then \
			if [ $$CURRENT_COVERAGE -lt $$BASELINE_COVERAGE ]; then \
				echo "FAIL: Coverage dropped from $$BASELINE_COVERAGE% to $$CURRENT_COVERAGE%"; \
				exit 1; \
			else \
				echo "SUCCESS: Coverage maintained or improved"; \
			fi; \
		else \
			echo "ERROR: Could not parse current coverage value"; \
			exit 1; \
		fi; \
	else \
		echo "No baseline coverage set. Use: BASELINE_COVERAGE=22 make test-coverage-compare"; \
		echo "Or run: make test-coverage-baseline"; \
		exit 1; \
	fi

# Create a baseline coverage file for comparison
test-coverage-baseline:
	@echo "Creating baseline coverage file..."
	pytest --cov=app --cov-report=term-missing --cov-report=html --cov-report=xml
	BASELINE_COVERAGE=$$(grep -o 'line-rate="[^"]*"' coverage.xml | head -1 | sed 's/line-rate="\([^"]*\)"/\1/' | awk '{printf "%.0f", $$1 * 100}'); \
	echo "Baseline coverage: $$BASELINE_COVERAGE%"; \
	echo "To use this baseline, run: BASELINE_COVERAGE=$$BASELINE_COVERAGE make test-coverage-compare"

# Run linting and then tests (for CI)
lint-test: lint-check test

# Database export/import tasks
# ─────────────────────────────────────────────────────────────────────────

# Export local database to SQL dump file
db-export:
	@echo "Exporting local ParadeDB database..."
	@if [ -z "$$POSTGRES_PASSWORD" ]; then \
		echo "ERROR: POSTGRES_PASSWORD environment variable is not set."; \
		echo "Please set it in a .env file or run: POSTGRES_PASSWORD=yourpass make db-export"; \
		exit 1; \
	fi
	@echo "Checking if ParadeDB container is running..."
	@if ! docker ps | grep -q btaa-geospatial-api-paradedb; then \
		echo "ERROR: ParadeDB container (btaa-geospatial-api-paradedb) is not running."; \
		echo "Start it with: docker-compose up -d paradedb"; \
		exit 1; \
	fi
	@echo "Container is running. Starting export..."
	@mkdir -p tmp
	@docker exec btaa-geospatial-api-paradedb pg_dump \
		-U postgres \
		-d btaa_geospatial_api \
		--no-owner \
		--no-acl \
		--clean \
		--if-exists \
		| gzip > tmp/btaa_geospatial_api_export.sql.gz
	@echo "Export complete: tmp/btaa_geospatial_api_export.sql.gz"
	@ls -lh tmp/btaa_geospatial_api_export.sql.gz

# Import database dump to remote server via Kamal
db-import:
	@echo "Importing database to remote PostgreSQL..."
	@if [ ! -f tmp/btaa_geospatial_api_export.sql.gz ]; then \
		echo "ERROR: Export file not found. Run 'make db-export' first."; \
		exit 1; \
	fi
	@if [ -z "$$KAMAL_SSH_USER" ] || [ -z "$$KAMAL_HOST" ]; then \
		echo "ERROR: KAMAL_SSH_USER and KAMAL_HOST environment variables must be set."; \
		echo "Please source your .kamal/secrets file or set these variables."; \
		exit 1; \
	fi
	@echo "Checking remote container status..."
	@ssh $$KAMAL_SSH_USER@$$KAMAL_HOST 'docker ps | grep btaa-geospatial-api-paradedb' || \
		(echo "ERROR: Remote paradedb container is not running. Check Kamal deployment." && exit 1)
	@echo "Remote container is running. Starting import..."
	@echo "⚠️  WARNING: This will drop and recreate all database objects!"
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	@echo "Copying dump file to remote server..."
	@scp tmp/btaa_geospatial_api_export.sql.gz $$KAMAL_SSH_USER@$$KAMAL_HOST:/var/tmp/
	@echo "Importing database..."
	@ssh $$KAMAL_SSH_USER@$$KAMAL_HOST '\
		gunzip -c /var/tmp/btaa_geospatial_api_export.sql.gz | \
		docker exec -i btaa-geospatial-api-paradedb psql \
			-U postgres \
			-d btaa_geospatial_api && \
		rm /var/tmp/btaa_geospatial_api_export.sql.gz'
	@echo "✓ Import complete!"

# Export and import in one command
db-sync: db-export db-import
	@echo "Database sync complete!"

# Search indexing tasks
# ─────────────────────────────────────────────────────────────────────────

# Reindex all resources into Elasticsearch
reindex:
	@echo "Reindexing all resources into Elasticsearch (same logic as /admin/reindex)..."
	@docker compose exec -T api bash -lc '\
		set -e; \
		: $${ELASTICSEARCH_INDEX:=btaa_geospatial_api}; \
		echo "Index: $$ELASTICSEARCH_INDEX"; \
		cd /app/backend && python scripts/reindex_admin.py'

# Ingest BTAA fixture JSON files into the DB (run inside api container).
# Usage: make ingest [FIXTURES_DIR=btaa_fixtures_data] [REPO_NAME=btaa_fixtures]
#   e.g. make ingest FIXTURES_DIR=btaa_featured_resources REPO_NAME=btaa_featured_resources
# After ingest, run: make reindex
FIXTURES_DIR ?= btaa_fixtures_data
REPO_NAME ?= btaa_fixtures
ingest:
	@echo "Ingesting fixtures from data/fixtures/$(FIXTURES_DIR) into database..."
	@docker compose exec -T api bash -lc '\
		cd /app/backend && python scripts/ingest_btaa_fixtures.py "$(FIXTURES_DIR)" "$(REPO_NAME)"'

# Ingest featured resources (btaa_featured_resources) then reindex into Elasticsearch
ingest-featured: FIXTURES_DIR := btaa_featured_resources
ingest-featured: REPO_NAME := btaa_featured_resources
ingest-featured:
	@echo "Ingesting btaa_featured_resources into database..."
	@docker compose exec -T api bash -lc 'cd /app/backend && python scripts/ingest_btaa_fixtures.py btaa_featured_resources btaa_featured_resources'
	@echo "Reindexing into Elasticsearch..."
	@$(MAKE) reindex

# Verify H3 pyramid fields (h3_res2..h3_res8, geo_or_near_global) in Elasticsearch
verify-h3-index:
	@echo "Verifying H3 pyramid fields in Elasticsearch..."
	@docker compose exec -T api bash -lc 'cd /app/backend && python scripts/verify_h3_index.py'

# (Old index_missing_resources target removed; resilient reindex handles verification/repair)

# Frontend (Docker dev): clear Vite cache and restart dev server.
# Use after changing optimizeDeps or when seeing "Failed to fetch dynamically imported module".
frontend-reset:
	@echo "Clearing Vite cache in frontend-dev and restarting..."
	@docker compose exec -T frontend-dev rm -rf /app/node_modules/.vite 2>/dev/null || true
	@docker compose restart frontend-dev
	@echo "Frontend dev server restarted."

# Cache management
clear_cache:
	@if [ -z "$(REDIS_PASSWORD)" ]; then \
		echo "ERROR: REDIS_PASSWORD is not set. Populate it in your .env file."; \
		exit 1; \
	fi
	@echo "Flushing Redis cache (database $(if $(REDIS_DB),$(REDIS_DB),0))..."
	@docker compose exec -T redis redis-cli -a "$(REDIS_PASSWORD)" -n $(if $(REDIS_DB),$(REDIS_DB),0) FLUSHDB
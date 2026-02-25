.PHONY: lint lint-check format test lint-test test-coverage-compare db-export db-import db-sync gbl-admin-db-download gbl-admin-db-unzip gbl-admin-db-restore gbl-admin-db-sync gbl-admin-db-add-latest-btaa-fields gbl-admin-db-import-resources populate-distributions populate-data-dictionaries gbl-admin-db-import-all reindex reindex-benchmark local-clear-search-cache es-unblock populate-relationships verify-h3-index kamal-reindex kamal-verify-h3-index kamal-clear-cache clear_cache frontend-reset ogm-refresh ogm-refresh-all ogm-refresh-repo ogm-status ogm-status-watch ogm-failures

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

# GBL Admin production dump restore defaults
GBL_ADMIN_SSH_USER ?= ewlarson
GBL_ADMIN_SSH_HOST ?= geomg.lib.umn.edu
GBL_ADMIN_REMOTE_DIR ?= /opt/data/pgdump
GBL_ADMIN_DUMP_GLOB ?= pgdump-geoportal_production-*.sql.gz
GBL_ADMIN_LOCAL_DIR ?= tmp
GBL_ADMIN_SQL_GLOB ?= pgdump-geoportal_production-*.sql
GBL_ADMIN_IMPORT_CONFLICT ?= update
GBL_ADMIN_DISTRIBUTIONS_BATCH_SIZE ?= 2000
KAMAL_APP_ROLE ?= web
KAMAL_PYTHON ?= /opt/venv/bin/python
# Local atomic reindex tuning.
REINDEX_CHUNK_SIZE ?= 2000
REINDEX_BULK_SIZE ?= 2000
REINDEX_BULK_MAX_RETRIES ?= 2
REINDEX_FAST_SETTINGS ?= true
REINDEX_FORCE_REPLICAS_ZERO ?= true
REINDEX_ALLOW_PARTIAL ?= false
REINDEX_PRUNE_OLD ?= true
REINDEX_RETAIN_PREVIOUS ?= 1
REINDEX_REMOVE_LEGACY_INDEX ?= true
REINDEX_BENCHMARK ?= false
# Kamal atomic reindex defaults (versioned index + alias swap + prune).
KAMAL_REINDEX_CHUNK_SIZE ?= 1000
KAMAL_REINDEX_BULK_SIZE ?= 2000
KAMAL_REINDEX_BULK_MAX_RETRIES ?= 2
KAMAL_REINDEX_FAST_SETTINGS ?= true
KAMAL_REINDEX_FORCE_REPLICAS_ZERO ?= true
KAMAL_REINDEX_ALLOW_PARTIAL ?= false
KAMAL_REINDEX_PRUNE_OLD ?= true
KAMAL_REINDEX_RETAIN_PREVIOUS ?= 1
KAMAL_REINDEX_REMOVE_LEGACY_INDEX ?= true
# Optional override for remote API base URL used by kamal-clear-cache.
# If unset, the target falls back to APPLICATION_URL from Kamal env.
KAMAL_API_URL ?=
KAMAL_CACHE_TYPE ?= search
OGM_API_URL ?= http://localhost:8000
OGM_STATUS_POLL_SECONDS ?= 5

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

# Download latest production GBL Admin SQL dump from remote host
gbl-admin-db-download:
	@echo "Resolving latest production GBL Admin dump..."
	@for cmd in ssh scp; do \
		if ! command -v $$cmd >/dev/null 2>&1; then \
			echo "ERROR: $$cmd is not installed or not on PATH."; \
			exit 1; \
		fi; \
	done
	@mkdir -p "$(GBL_ADMIN_LOCAL_DIR)"
	@REMOTE_DUMP=$$(ssh $(GBL_ADMIN_SSH_USER)@$(GBL_ADMIN_SSH_HOST) "ls -1t $(GBL_ADMIN_REMOTE_DIR)/$(GBL_ADMIN_DUMP_GLOB) 2>/dev/null | head -n 1"); \
	if [ -z "$$REMOTE_DUMP" ]; then \
		echo "ERROR: No remote dump matched $(GBL_ADMIN_REMOTE_DIR)/$(GBL_ADMIN_DUMP_GLOB)."; \
		exit 1; \
	fi; \
	echo "Latest dump: $$REMOTE_DUMP"; \
	scp "$(GBL_ADMIN_SSH_USER)@$(GBL_ADMIN_SSH_HOST):$$REMOTE_DUMP" "$(GBL_ADMIN_LOCAL_DIR)/"; \
	LOCAL_GZ="$(GBL_ADMIN_LOCAL_DIR)/$$(basename "$$REMOTE_DUMP")"; \
	echo "Downloaded dump: $$LOCAL_GZ"

# Decompress latest downloaded production GBL Admin dump (writes full .sql to disk; prefer gbl-admin-db-sync which streams)
gbl-admin-db-unzip:
	@echo "Decompressing latest production GBL Admin dump..."
	@if ! command -v gunzip >/dev/null 2>&1; then \
		echo "ERROR: gunzip is not installed or not on PATH."; \
		exit 1; \
	fi
	@LOCAL_GZ=$$(ls -1t "$(GBL_ADMIN_LOCAL_DIR)"/$(GBL_ADMIN_DUMP_GLOB) 2>/dev/null | head -n 1); \
	if [ -z "$$LOCAL_GZ" ]; then \
		echo "ERROR: No local dump found in $(GBL_ADMIN_LOCAL_DIR) matching $(GBL_ADMIN_DUMP_GLOB)."; \
		echo "Run 'make gbl-admin-db-download' first."; \
		exit 1; \
	fi; \
	LOCAL_SQL="$${LOCAL_GZ%.gz}"; \
	echo "Using dump: $$LOCAL_GZ"; \
	gunzip -c "$$LOCAL_GZ" > "$$LOCAL_SQL" || { echo "ERROR: gunzip failed (check disk space)."; exit 1; }; \
	echo "Decompressed SQL: $$LOCAL_SQL"

# Restore production GBL Admin dump to local ParadeDB. Uses .sql if present, otherwise streams from .gz (no extra disk).
gbl-admin-db-restore:
	@echo "Restoring production GBL Admin SQL into local ParadeDB..."
	@if ! command -v docker >/dev/null 2>&1; then \
		echo "ERROR: docker is not installed or not on PATH."; \
		exit 1; \
	fi
	@if [ -z "$$(docker compose ps --status running --services paradedb 2>/dev/null)" ]; then \
		echo "ERROR: paradedb service is not running."; \
		echo "Start it with: docker compose up -d paradedb"; \
		exit 1; \
	fi
	@LOCAL_SQL=$$(ls -1t "$(GBL_ADMIN_LOCAL_DIR)"/$(GBL_ADMIN_SQL_GLOB) 2>/dev/null | head -n 1); \
	LOCAL_GZ=$$(ls -1t "$(GBL_ADMIN_LOCAL_DIR)"/$(GBL_ADMIN_DUMP_GLOB) 2>/dev/null | head -n 1); \
	if [ -n "$$LOCAL_SQL" ]; then \
		SOURCE="$$LOCAL_SQL"; \
		DUMP_DATE=$$(basename "$$LOCAL_SQL" | sed -E 's/^pgdump-geoportal_production-([0-9]{8})\.sql$$/\1/'); \
	elif [ -n "$$LOCAL_GZ" ]; then \
		SOURCE="$$LOCAL_GZ"; \
		DUMP_DATE=$$(basename "$$LOCAL_GZ" | sed -E 's/^pgdump-geoportal_production-([0-9]{8})\.sql\.gz$$/\1/'); \
	else \
		echo "ERROR: No dump found in $(GBL_ADMIN_LOCAL_DIR) (need $(GBL_ADMIN_SQL_GLOB) or $(GBL_ADMIN_DUMP_GLOB))."; \
		echo "Run 'make gbl-admin-db-download' first."; \
		exit 1; \
	fi; \
	if ! echo "$$DUMP_DATE" | grep -Eq '^[0-9]{8}$$'; then \
		echo "ERROR: Could not parse dump date from $$SOURCE."; \
		exit 1; \
	fi; \
	DB_NAME="geoportal_production_$$DUMP_DATE"; \
	echo "Target DB: $$DB_NAME"; \
	docker compose exec -T paradedb psql -U postgres -d postgres -c "CREATE ROLE geomg;" 2>/dev/null || true; \
	docker compose exec -T paradedb psql -U postgres -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$$DB_NAME' AND pid <> pg_backend_pid();" || true; \
	docker compose exec -T paradedb psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS \"$$DB_NAME\";"; \
	docker compose exec -T paradedb psql -U postgres -d postgres -c "CREATE DATABASE \"$$DB_NAME\" OWNER postgres;"; \
	if [ -n "$$LOCAL_SQL" ]; then \
		echo "Restoring from decompressed SQL: $$LOCAL_SQL"; \
		cat "$$LOCAL_SQL" | docker compose exec -T paradedb psql -U postgres -d "$$DB_NAME"; \
	else \
		echo "Streaming from compressed dump: $$LOCAL_GZ (no extra disk used)"; \
		gunzip -c "$$LOCAL_GZ" | docker compose exec -T paradedb psql -U postgres -d "$$DB_NAME"; \
	fi; \
	echo "Restore complete."; \
	echo "Dump used: $$SOURCE"; \
	echo "Created DB: $$DB_NAME"; \
	echo "Creating kithe_to_resources_bridge materialized view in restored GBL Admin DB..."; \
	DB_PASSWORD=$$(docker compose exec -T paradedb bash -lc 'printf %s "$$POSTGRES_PASSWORD"'); \
	if [ -z "$$DB_PASSWORD" ]; then \
		DB_PASSWORD="$(POSTGRES_PASSWORD)"; \
		DB_PASSWORD="$${DB_PASSWORD#\"}"; \
		DB_PASSWORD="$${DB_PASSWORD%\"}"; \
		DB_PASSWORD="$${DB_PASSWORD#\'}"; \
		DB_PASSWORD="$${DB_PASSWORD%\'}"; \
	fi; \
	docker compose exec -T \
		-e OLD_DB_NAME="$$DB_NAME" \
		-e DB_HOST="paradedb" \
		-e DB_PORT="5432" \
		-e DB_USER="postgres" \
		-e DB_PASSWORD="$$DB_PASSWORD" \
		api bash -lc 'cd /app/backend && python db/migrations/bridge_old_production.py --create-view'

# End-to-end: download latest dump and restore (streams from .gz; no decompression to disk)
gbl-admin-db-sync: gbl-admin-db-download gbl-admin-db-restore
	@echo "GBL Admin database sync complete!"

# Add latest BTAA schema compatibility fields to resources table.
gbl-admin-db-add-latest-btaa-fields:
	@echo "Adding latest BTAA schema fields to resources table..."
	@docker compose exec -T api bash -lc 'cd /app/backend && python db/migrations/add_latest_btaa_schema_fields.py'

# Import resources from kithe_to_resources_bridge into btaa_geospatial_api.
# Uses the latest restored geoportal_production_* DB if OLD_DB_NAME is unset.
gbl-admin-db-import-resources:
	@echo "Importing resources from GBL Admin bridge view..."
	@RESOLVED_OLD_DB_NAME="$$OLD_DB_NAME"; \
	if [ -n "$$RESOLVED_OLD_DB_NAME" ]; then \
		FOUND_DB=$$(docker compose exec -T paradedb psql -U postgres -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = '$$RESOLVED_OLD_DB_NAME';"); \
		if [ "$$FOUND_DB" != "1" ]; then \
			echo "WARN: OLD_DB_NAME=$$RESOLVED_OLD_DB_NAME not found; auto-detecting latest geoportal_production_* DB."; \
			RESOLVED_OLD_DB_NAME=""; \
		fi; \
	fi; \
	if [ -z "$$RESOLVED_OLD_DB_NAME" ]; then \
		RESOLVED_OLD_DB_NAME=$$(docker compose exec -T paradedb psql -U postgres -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'geoportal_production_%' ORDER BY datname DESC LIMIT 1;"); \
	fi; \
	if [ -z "$$RESOLVED_OLD_DB_NAME" ]; then \
		echo "ERROR: Could not resolve OLD_DB_NAME (no geoportal_production_* database found)."; \
		exit 1; \
	fi; \
	DB_PASSWORD=$$(docker compose exec -T paradedb bash -lc 'printf %s "$$POSTGRES_PASSWORD"'); \
	if [ -z "$$DB_PASSWORD" ]; then \
		echo "ERROR: Could not read POSTGRES_PASSWORD from paradedb container."; \
		exit 1; \
	fi; \
	echo "OLD_DB_NAME=$$RESOLVED_OLD_DB_NAME"; \
	docker compose exec -T \
		-e OLD_DB_NAME="$$RESOLVED_OLD_DB_NAME" \
		-e DB_NAME="btaa_geospatial_api" \
		-e DB_HOST="paradedb" \
		-e DB_PORT="5432" \
		-e DB_USER="postgres" \
		-e DB_PASSWORD="$$DB_PASSWORD" \
		api bash -lc 'cd /app/backend && python db/migrations/import_from_old_production.py --conflict $(GBL_ADMIN_IMPORT_CONFLICT) --verify'

# Populate resource_distributions from legacy document_distributions.
# Uses the latest restored geoportal_production_* DB if OLD_DB_NAME is unset.
populate-distributions:
	@echo "Populating resource_distributions from legacy document_distributions..."
	@RESOLVED_OLD_DB_NAME="$$OLD_DB_NAME"; \
	if [ -n "$$RESOLVED_OLD_DB_NAME" ]; then \
		FOUND_DB=$$(docker compose exec -T paradedb psql -U postgres -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = '$$RESOLVED_OLD_DB_NAME';"); \
		if [ "$$FOUND_DB" != "1" ]; then \
			echo "WARN: OLD_DB_NAME=$$RESOLVED_OLD_DB_NAME not found; auto-detecting latest geoportal_production_* DB."; \
			RESOLVED_OLD_DB_NAME=""; \
		fi; \
	fi; \
	if [ -z "$$RESOLVED_OLD_DB_NAME" ]; then \
		RESOLVED_OLD_DB_NAME=$$(docker compose exec -T paradedb psql -U postgres -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'geoportal_production_%' ORDER BY datname DESC LIMIT 1;"); \
	fi; \
	if [ -z "$$RESOLVED_OLD_DB_NAME" ]; then \
		echo "ERROR: Could not resolve OLD_DB_NAME (no geoportal_production_* database found)."; \
		exit 1; \
	fi; \
	DB_PASSWORD=$$(docker compose exec -T paradedb bash -lc 'printf %s "$$POSTGRES_PASSWORD"'); \
	if [ -z "$$DB_PASSWORD" ]; then \
		echo "ERROR: Could not read POSTGRES_PASSWORD from paradedb container."; \
		exit 1; \
	fi; \
	echo "OLD_DB_NAME=$$RESOLVED_OLD_DB_NAME"; \
	docker compose exec -T \
		-e OLD_DB_NAME="$$RESOLVED_OLD_DB_NAME" \
		-e DB_NAME="btaa_geospatial_api" \
		-e DB_HOST="paradedb" \
		-e DB_PORT="5432" \
		-e DB_USER="postgres" \
		-e DB_PASSWORD="$$DB_PASSWORD" \
		api bash -lc 'cd /app/backend && python db/migrations/migrate_document_distributions.py --batch-size $(GBL_ADMIN_DISTRIBUTIONS_BATCH_SIZE)'

# Populate resource_data_dictionaries and resource_data_dictionary_entries from legacy tables.
# Uses the latest restored geoportal_production_* DB if OLD_DB_NAME is unset.
populate-data-dictionaries:
	@echo "Populating resource_data_dictionaries from legacy document_data_dictionaries..."
	@RESOLVED_OLD_DB_NAME="$$OLD_DB_NAME"; \
	if [ -n "$$RESOLVED_OLD_DB_NAME" ]; then \
		FOUND_DB=$$(docker compose exec -T paradedb psql -U postgres -d postgres -Atc "SELECT 1 FROM pg_database WHERE datname = '$$RESOLVED_OLD_DB_NAME';"); \
		if [ "$$FOUND_DB" != "1" ]; then \
			echo "WARN: OLD_DB_NAME=$$RESOLVED_OLD_DB_NAME not found; auto-detecting latest geoportal_production_* DB."; \
			RESOLVED_OLD_DB_NAME=""; \
		fi; \
	fi; \
	if [ -z "$$RESOLVED_OLD_DB_NAME" ]; then \
		RESOLVED_OLD_DB_NAME=$$(docker compose exec -T paradedb psql -U postgres -d postgres -Atc "SELECT datname FROM pg_database WHERE datname LIKE 'geoportal_production_%' ORDER BY datname DESC LIMIT 1;"); \
	fi; \
	if [ -z "$$RESOLVED_OLD_DB_NAME" ]; then \
		echo "ERROR: Could not resolve OLD_DB_NAME (no geoportal_production_* database found)."; \
		exit 1; \
	fi; \
	DB_PASSWORD=$$(docker compose exec -T paradedb bash -lc 'printf %s "$$POSTGRES_PASSWORD"'); \
	if [ -z "$$DB_PASSWORD" ]; then \
		echo "ERROR: Could not read POSTGRES_PASSWORD from paradedb container."; \
		exit 1; \
	fi; \
	echo "OLD_DB_NAME=$$RESOLVED_OLD_DB_NAME"; \
	docker compose exec -T \
		-e OLD_DB_NAME="$$RESOLVED_OLD_DB_NAME" \
		-e DB_NAME="btaa_geospatial_api" \
		-e DB_HOST="paradedb" \
		-e DB_PORT="5432" \
		-e DB_USER="postgres" \
		-e DB_PASSWORD="$$DB_PASSWORD" \
		api bash -lc 'cd /app/backend && python db/migrations/migrate_resource_data_dictionaries.py'

# Full GBL Admin import pipeline after restore.
gbl-admin-db-import-all: gbl-admin-db-add-latest-btaa-fields gbl-admin-db-import-resources populate-distributions populate-data-dictionaries populate-relationships reindex
	@echo "GBL Admin full import pipeline complete!"

# Search indexing tasks
# ─────────────────────────────────────────────────────────────────────────

# Clear Elasticsearch read-only block (after freeing disk space post flood-stage).
# Run this when reindex fails with "flood stage disk watermark exceeded"; then run make reindex.
es-unblock:
	@echo "Clearing read-only block on all Elasticsearch indices..."
	@docker compose exec -T elasticsearch curl -s -X PUT "http://localhost:9200/_all/_settings" \
		-H "Content-Type: application/json" \
		-d '{"index.blocks.read_only_allow_delete": null}' || true
	@echo "Done. Run 'make reindex' if you need to reindex."

# Reindex all resources into Elasticsearch using versioned index + alias swap.
reindex:
	@echo "Atomic reindex (versioned index + alias swap) in local Docker..."
	@docker compose exec -T api bash -lc '\
		set -e; \
		: $${ELASTICSEARCH_INDEX:=btaa_geospatial_api}; \
		echo "Alias: $$ELASTICSEARCH_INDEX"; \
		cd /app/backend && \
		REINDEX_ATOMIC_CHUNK_SIZE=$(REINDEX_CHUNK_SIZE) \
		REINDEX_ATOMIC_BULK_SIZE=$(REINDEX_BULK_SIZE) \
		REINDEX_ATOMIC_BULK_MAX_RETRIES=$(REINDEX_BULK_MAX_RETRIES) \
		REINDEX_ATOMIC_FAST_SETTINGS=$(REINDEX_FAST_SETTINGS) \
		REINDEX_ATOMIC_FORCE_REPLICAS_ZERO=$(REINDEX_FORCE_REPLICAS_ZERO) \
		REINDEX_ATOMIC_ALLOW_PARTIAL=$(REINDEX_ALLOW_PARTIAL) \
		REINDEX_ATOMIC_PRUNE_OLD=$(REINDEX_PRUNE_OLD) \
		REINDEX_ATOMIC_RETAIN_PREVIOUS=$(REINDEX_RETAIN_PREVIOUS) \
		REINDEX_ATOMIC_REMOVE_LEGACY_INDEX=$(REINDEX_REMOVE_LEGACY_INDEX) \
		REINDEX_ATOMIC_BENCHMARK=$(REINDEX_BENCHMARK) \
		python3 scripts/reindex_atomic.py'
	@echo "Reindex complete; clearing local search cache..."
	@$(MAKE) local-clear-search-cache

# Reindex with benchmark timing output enabled.
reindex-benchmark:
	@$(MAKE) reindex REINDEX_BENCHMARK=true

# Clear local API search cache via admin endpoint.
local-clear-search-cache:
	@docker compose exec -T api bash -lc 'ADMIN_USER=$${ADMIN_USERNAME:-admin}; ADMIN_PASS=$${ADMIN_PASSWORD:-changeme}; curl -fsS -u "$$ADMIN_USER:$$ADMIN_PASS" -X POST "http://localhost:8000/api/v1/admin/cache/clear?cache_type=search"'

# Refresh OpenGeoMetadata (OGM) harvest for all enabled weekly repos.
# Uses ADMIN_USERNAME/ADMIN_PASSWORD from env or .env (defaults to admin/changeme).
ogm-refresh: ogm-refresh-all

ogm-refresh-all:
	@echo "Triggering OGM harvest for all enabled weekly repos via $(OGM_API_URL)..."
	@docker compose exec -T api bash -lc '\
		ADMIN_USER=$${ADMIN_USERNAME:-admin}; \
		ADMIN_PASS=$${ADMIN_PASSWORD:-changeme}; \
		curl -fsS -u "$$ADMIN_USER:$$ADMIN_PASS" -X POST \
			"$(OGM_API_URL)/api/v1/admin/ogm/harvest" \
			-H "Content-Type: application/json" \
			-d '\''{"ogm_all":true,"ogm_trigger":"weekly"}'\'''
	@echo
	@echo "OGM harvest request submitted."

# Refresh a single OpenGeoMetadata (OGM) repo.
# Usage: make ogm-refresh-repo OGM_REPO_NAME=edu.stanford.purl
ogm-refresh-repo:
	@if [ -z "$(OGM_REPO_NAME)" ]; then \
		echo "ERROR: OGM_REPO_NAME is required."; \
		echo "Usage: make ogm-refresh-repo OGM_REPO_NAME=edu.stanford.purl"; \
		exit 1; \
	fi
	@echo "Triggering OGM harvest for repo $(OGM_REPO_NAME) via $(OGM_API_URL)..."
	@docker compose exec -T api bash -lc '\
		ADMIN_USER=$${ADMIN_USERNAME:-admin}; \
		ADMIN_PASS=$${ADMIN_PASSWORD:-changeme}; \
		curl -fsS -u "$$ADMIN_USER:$$ADMIN_PASS" -X POST \
			"$(OGM_API_URL)/api/v1/admin/ogm/harvest" \
			-H "Content-Type: application/json" \
			-d "{\"ogm_repo_name\":\"$(OGM_REPO_NAME)\",\"ogm_trigger\":\"manual\"}"'
	@echo
	@echo "OGM harvest request submitted for $(OGM_REPO_NAME)."

# Show OGM harvest status snapshot.
# Usage:
#   make ogm-status                      # list recent runs
#   make ogm-status OGM_RUN_ID=<run_id> # show one run detail
ogm-status:
	@echo "Fetching OGM harvest status from $(OGM_API_URL)..."
	@docker compose exec -T api bash -lc '\
		ADMIN_USER=$${ADMIN_USERNAME:-admin}; \
		ADMIN_PASS=$${ADMIN_PASSWORD:-changeme}; \
		if [ -n "$(OGM_RUN_ID)" ]; then \
			curl -fsS -u "$$ADMIN_USER:$$ADMIN_PASS" \
				"$(OGM_API_URL)/api/v1/admin/ogm/harvest/runs/$(OGM_RUN_ID)"; \
		else \
			curl -fsS -u "$$ADMIN_USER:$$ADMIN_PASS" \
				"$(OGM_API_URL)/api/v1/admin/ogm/harvest/runs"; \
		fi'
	@echo

# Continuously poll OGM harvest status.
# Usage:
#   make ogm-status-watch
#   make ogm-status-watch OGM_RUN_ID=<run_id> OGM_STATUS_POLL_SECONDS=3
ogm-status-watch:
	@echo "Watching OGM harvest status (every $(OGM_STATUS_POLL_SECONDS)s). Press Ctrl+C to stop."
	@while true; do \
		$(MAKE) --no-print-directory ogm-status OGM_RUN_ID="$(OGM_RUN_ID)"; \
		sleep $(OGM_STATUS_POLL_SECONDS); \
	done

# Show only failed OGM harvest runs with error details.
# Usage: make ogm-failures
ogm-failures:
	@echo "Fetching failed OGM harvest runs from $(OGM_API_URL)..."
	@docker compose exec -T api bash -lc '\
		ADMIN_USER=$${ADMIN_USERNAME:-admin}; \
		ADMIN_PASS=$${ADMIN_PASSWORD:-changeme}; \
		curl -fsS -u "$$ADMIN_USER:$$ADMIN_PASS" \
			"$(OGM_API_URL)/api/v1/admin/ogm/harvest/runs" \
		| python -c "import json,sys; data=json.load(sys.stdin); failed=[r for r in data.get(\"runs\",[]) if r.get(\"ogm_status\")==\"failed\"]; print(\"No failed OGM runs found in current history window.\") if not failed else [print(\"ogm_id={0} repo={1} trigger={2} started_at={3}\\nerror={4}\\n\".format(r.get(\"ogm_id\"), r.get(\"ogm_repo_name\"), r.get(\"ogm_trigger\"), r.get(\"ogm_started_at\"), r.get(\"ogm_error\") or \"(none)\")) for r in failed]"'

# Populate resource_relationships from resources table (dct_isPartOf_sm, pcdm_memberOf_sm, etc.).
# Run after ingest or when relationship columns change. Search "Has part" filter uses DB + ES;
# reindex copies resources.dct_isPartOf_sm into Elasticsearch for filtering.
populate-relationships:
	@echo "Populating resource_relationships from resources table..."
	@docker compose exec -T api bash -lc 'cd /app/backend && python scripts/populate_relationships.py'

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
	@docker compose exec -T api bash -lc 'cd /app/backend && python3 scripts/verify_h3_index.py'

# Reindex all resources into Elasticsearch on Kamal (single role run by default).
kamal-reindex:
	@echo "Atomic reindex on Kamal (role: $(KAMAL_APP_ROLE))..."
	@if [ -z "$$KAMAL_SSH_USER" ] || [ -z "$$KAMAL_HOST" ]; then \
		echo "ERROR: KAMAL_SSH_USER and KAMAL_HOST environment variables must be set."; \
		echo "Please source .kamal/secrets first."; \
		exit 1; \
	fi
	@kamal app exec --roles $(KAMAL_APP_ROLE) "bash -lc 'cd /app/backend && \
		REINDEX_ATOMIC_CHUNK_SIZE=$(KAMAL_REINDEX_CHUNK_SIZE) \
		REINDEX_ATOMIC_BULK_SIZE=$(KAMAL_REINDEX_BULK_SIZE) \
		REINDEX_ATOMIC_BULK_MAX_RETRIES=$(KAMAL_REINDEX_BULK_MAX_RETRIES) \
		REINDEX_ATOMIC_FAST_SETTINGS=$(KAMAL_REINDEX_FAST_SETTINGS) \
		REINDEX_ATOMIC_FORCE_REPLICAS_ZERO=$(KAMAL_REINDEX_FORCE_REPLICAS_ZERO) \
		REINDEX_ATOMIC_ALLOW_PARTIAL=$(KAMAL_REINDEX_ALLOW_PARTIAL) \
		REINDEX_ATOMIC_PRUNE_OLD=$(KAMAL_REINDEX_PRUNE_OLD) \
		REINDEX_ATOMIC_RETAIN_PREVIOUS=$(KAMAL_REINDEX_RETAIN_PREVIOUS) \
		REINDEX_ATOMIC_REMOVE_LEGACY_INDEX=$(KAMAL_REINDEX_REMOVE_LEGACY_INDEX) \
		$(KAMAL_PYTHON) scripts/reindex_atomic.py'"
	@echo "Reindex complete; clearing API cache (cache_type: $(KAMAL_CACHE_TYPE))..."
	@$(MAKE) kamal-clear-cache

# Verify H3 pyramid fields on Kamal (single role run by default).
kamal-verify-h3-index:
	@echo "Verifying H3 pyramid fields on Kamal (role: $(KAMAL_APP_ROLE))..."
	@if [ -z "$$KAMAL_SSH_USER" ] || [ -z "$$KAMAL_HOST" ]; then \
		echo "ERROR: KAMAL_SSH_USER and KAMAL_HOST environment variables must be set."; \
		echo "Please source .kamal/secrets first."; \
		exit 1; \
	fi
	@kamal app exec --roles $(KAMAL_APP_ROLE) "bash -lc 'cd /app/backend && $(KAMAL_PYTHON) scripts/verify_h3_index.py'"

# Clear API cache on Kamal via admin endpoint (defaults to search cache).
# Usage:
#   make kamal-clear-cache
#   make kamal-clear-cache KAMAL_CACHE_TYPE=all
#   make kamal-clear-cache KAMAL_CACHE_TYPE=suggest
kamal-clear-cache:
	@echo "Clearing remote cache on Kamal (role: $(KAMAL_APP_ROLE), cache_type: $(KAMAL_CACHE_TYPE))..."
	@if [ -z "$$KAMAL_SSH_USER" ] || [ -z "$$KAMAL_HOST" ]; then \
		echo "ERROR: KAMAL_SSH_USER and KAMAL_HOST environment variables must be set."; \
		echo "Please source .kamal/secrets first."; \
		exit 1; \
	fi
	@kamal app exec --roles $(KAMAL_APP_ROLE) "bash -lc 'ADMIN_USER=\$${ADMIN_USERNAME:-admin}; ADMIN_PASS=\$${ADMIN_PASSWORD:-changeme}; API_BASE=\"$(KAMAL_API_URL)\"; if [ -z \"\$$API_BASE\" ]; then API_BASE=\"\$$APPLICATION_URL\"; fi; if [ -z \"\$$API_BASE\" ]; then echo \"ERROR: KAMAL_API_URL or APPLICATION_URL must be set.\"; exit 1; fi; API_BASE=\"\$${API_BASE%/}\"; curl -fsS -u \"\$$ADMIN_USER:\$$ADMIN_PASS\" -X POST \"\$$API_BASE/api/v1/admin/cache/clear?cache_type=$(KAMAL_CACHE_TYPE)\"'"
	@echo
	@echo "Remote cache clear request submitted."

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
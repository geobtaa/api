.PHONY: lint lint-check format test lint-test test-coverage-compare db-export db-import db-sync

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

# Run both linting and formatting checks (without modifying files)
lint:
	@echo "Checking code with ruff..."
	ruff check app/ tests/ scripts/

# Format code in-place
format:
	@echo "Formatting code with ruff..."
	ruff format app/ tests/ scripts/
	ruff check --fix app/ tests/ scripts/

# Check formatting only (for CI)
lint-check:
	@echo "Checking formatting with ruff..."
	ruff format --check app/ tests/ scripts/
	ruff check app/ tests/ scripts/

# Run just the tests with coverage threshold
test:
	@echo "Setting up test database..."
	@echo "Checking if test database exists..."
	@if docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -lqt | cut -d \| -f 1 | grep -qw btaa_ogm_api_test'; then \
		echo "Test database already exists, skipping clone..."; \
	else \
		echo "Test database does not exist, cloning from production..."; \
		docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '"'"'btaa_ogm_api'"'"' AND pid <> pg_backend_pid();"' || true; \
		docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -c "CREATE DATABASE btaa_ogm_api_test WITH TEMPLATE btaa_ogm_api OWNER postgres;"'; \
	fi
	@echo "Running tests with coverage threshold of $(COVERAGE_THRESHOLD)%..."
	pytest --cov=app --cov-report=term-missing --cov-report=html --cov-fail-under=$(COVERAGE_THRESHOLD)

# Run just the tests without coverage threshold (for debugging)
test-no-coverage:
	@echo "Running tests without coverage threshold..."
	pytest --full-trace

# Force a fresh clone of the test database
test-fresh-db:
	@echo "Force cloning fresh test database..."
	@docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '"'"'btaa_ogm_api'"'"' AND pid <> pg_backend_pid();"' || true
	@docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -c "DROP DATABASE IF EXISTS btaa_ogm_api_test;"' || true
	@docker compose exec -T paradedb bash -lc 'PGPASSWORD=$$POSTGRES_PASSWORD psql -U postgres -c "CREATE DATABASE btaa_ogm_api_test WITH TEMPLATE btaa_ogm_api OWNER postgres;"'
	@echo "Fresh test database created!"

# Run tests and compare coverage against previous run (fails if coverage drops)
test-coverage-compare:
	@echo "Running tests with coverage comparison..."
	@if [ -n "$$BASELINE_COVERAGE" ]; then \
		echo "Baseline coverage: $$BASELINE_COVERAGE%"; \
		pytest --cov=app --cov-report=term-missing --cov-report=html --cov-report=xml; \
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
	@if ! docker ps | grep -q btaa-ogm-api-paradedb; then \
		echo "ERROR: ParadeDB container (btaa-ogm-api-paradedb) is not running."; \
		echo "Start it with: docker-compose up -d paradedb"; \
		exit 1; \
	fi
	@echo "Container is running. Starting export..."
	@mkdir -p tmp
	@docker exec btaa-ogm-api-paradedb pg_dump \
		-U postgres \
		-d btaa_ogm_api \
		--no-owner \
		--no-acl \
		--clean \
		--if-exists \
		| gzip > tmp/btaa_ogm_api_export.sql.gz
	@echo "Export complete: tmp/btaa_ogm_api_export.sql.gz"
	@ls -lh tmp/btaa_ogm_api_export.sql.gz

# Import database dump to remote server via Kamal
db-import:
	@echo "Importing database to remote PostgreSQL..."
	@if [ ! -f tmp/btaa_ogm_api_export.sql.gz ]; then \
		echo "ERROR: Export file not found. Run 'make db-export' first."; \
		exit 1; \
	fi
	@if [ -z "$$KAMAL_SSH_USER" ] || [ -z "$$KAMAL_HOST" ]; then \
		echo "ERROR: KAMAL_SSH_USER and KAMAL_HOST environment variables must be set."; \
		echo "Please source your .kamal/secrets file or set these variables."; \
		exit 1; \
	fi
	@echo "Checking remote container status..."
	@ssh $$KAMAL_SSH_USER@$$KAMAL_HOST 'docker ps | grep btaa-data-api-paradedb' || \
		(echo "ERROR: Remote paradedb container is not running. Check Kamal deployment." && exit 1)
	@echo "Remote container is running. Starting import..."
	@echo "⚠️  WARNING: This will drop and recreate all database objects!"
	@echo "Press Ctrl+C within 5 seconds to cancel..."
	@sleep 5
	@echo "Copying dump file to remote server..."
	@scp tmp/btaa_ogm_api_export.sql.gz $$KAMAL_SSH_USER@$$KAMAL_HOST:/tmp/
	@echo "Importing database..."
	@ssh $$KAMAL_SSH_USER@$$KAMAL_HOST '\
		gunzip -c /tmp/btaa_ogm_api_export.sql.gz | \
		docker exec -i btaa-data-api-paradedb psql \
			-U postgres \
			-d btaa_ogm_api && \
		rm /tmp/btaa_ogm_api_export.sql.gz'
	@echo "✓ Import complete!"

# Export and import in one command
db-sync: db-export db-import
	@echo "Database sync complete!"
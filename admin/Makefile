.PHONY: help install dev down build lint format format-check test coverage check \
	backend-lint backend-format backend-format-check backend-test backend-coverage \
	frontend-lint frontend-format frontend-format-check frontend-test frontend-coverage \
	backend-migrate test-db-down

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "; printf "Usage: make <target>\n\n"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install locked backend and frontend dependencies
	cd backend && uv sync --frozen --extra dev
	cd frontend && npm ci

dev: ## Start the full local application with fresh Docker bases
	docker compose up --build --pull always

down: ## Stop the local Docker application
	docker compose down

build: ## Build the production application image
	docker build --pull --target production -t geomg-admin:local .

backend-lint: ## Lint backend Python
	cd backend && uv run ruff check app tests migrations ../scripts/link_resource_sources.py ../scripts/recover_resource_sources.py ../scripts/link_resource_sets.py ../scripts/local_admin_api.py

backend-format: ## Format and safely fix backend Python
	cd backend && uv run ruff format app tests migrations ../scripts/link_resource_sources.py ../scripts/recover_resource_sources.py ../scripts/link_resource_sets.py ../scripts/local_admin_api.py
	cd backend && uv run ruff check --fix app tests migrations ../scripts/link_resource_sources.py ../scripts/recover_resource_sources.py ../scripts/link_resource_sets.py ../scripts/local_admin_api.py

backend-format-check: ## Check backend formatting without edits
	cd backend && uv run ruff format --check app tests migrations ../scripts/link_resource_sources.py ../scripts/recover_resource_sources.py ../scripts/link_resource_sets.py ../scripts/local_admin_api.py

backend-test: ## Run backend tests with disposable PostgreSQL
	sh scripts/run_backend_tests.sh

backend-coverage: ## Run backend tests with HTML and XML coverage reports
	sh scripts/run_backend_tests.sh --cov=app --cov-report=term-missing --cov-report=html:coverage_html_report --cov-report=xml --cov-fail-under=90

test-db-down: ## Remove only the disposable integration database
	docker compose -f compose.test.yaml down

backend-migrate: ## Apply local development migrations explicitly
	cd backend && uv run alembic upgrade head

frontend-lint: ## Lint frontend TypeScript
	cd frontend && npm run lint

frontend-format: ## Format frontend source
	cd frontend && npm run format

frontend-format-check: ## Check frontend formatting without edits
	cd frontend && npm run format:check

frontend-test: ## Run frontend tests
	cd frontend && npm test

frontend-coverage: ## Run frontend tests with coverage reports
	cd frontend && npm run test:coverage

lint: backend-lint frontend-lint ## Lint the entire project

format: backend-format frontend-format ## Format the entire project

format-check: backend-format-check frontend-format-check ## Check formatting

test: backend-test frontend-test ## Run all tests

coverage: backend-coverage frontend-coverage ## Generate all coverage reports

check: lint format-check coverage ## Run the local CI checks

.PHONY: fixtures-check
fixtures-check: ## Verify bundled Geoportal fixtures and unique starter IDs
	cd backend && uv run python -m app.fixtures

.PHONY: backend-worker
backend-worker: ## Run the durable worker with local development identity
	cd backend && uv run python -m app.jobs.worker

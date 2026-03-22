.PHONY: help lint lint-check format test test-no-coverage

# Coverage threshold
COVERAGE_THRESHOLD ?= 50

# List all make targets with descriptions
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-35s\033[0m %s\n", $$1, $$2}'

# Run both linting and formatting checks (without modifying files)
lint: ## Check code with ruff (no modifications)
	@echo "Checking code with ruff..."
	ruff check .

# Check formatting only (for CI)
lint-check: ## CI-style lint/format check (no edits)
	@echo "Checking formatting with ruff..."
	ruff format --check .
	ruff check .

# Format code in-place
format: ## Format and fix code with ruff
	@echo "Formatting code with ruff..."
	ruff format .
	ruff check --fix .

# Run tests with coverage threshold
test: ## Run tests with coverage threshold
	@echo "Running tests with coverage threshold of $(COVERAGE_THRESHOLD)%..."
	pytest --cov=. --cov-report=term-missing --cov-report=html --cov-fail-under=$(COVERAGE_THRESHOLD)

# Run tests without coverage
test-no-coverage: ## Run tests without coverage threshold
	@echo "Running tests without coverage threshold..."
	pytest -v

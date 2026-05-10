.PHONY: test test-unit test-integration lint format build man docs

PYTHON ?= python3
RUFF ?= ruff

test: ## Run the full CLI test suite
	$(PYTHON) -m pytest

test-unit: ## Run unit tests
	$(PYTHON) -m pytest -m "not integration"

test-integration: ## Run integration-style mocked-flow tests
	$(PYTHON) -m pytest -m integration

lint: ## Check CLI code
	$(RUFF) format --check src tests
	$(RUFF) check src tests

format: ## Format CLI code
	$(RUFF) format src tests
	$(RUFF) check --fix src tests

build: ## Build source and wheel distributions
	$(PYTHON) -m build

man: ## Refresh generated man pages from Markdown sources
	@mkdir -p man
	@for file in docs/*.1.md; do \
		name=$$(basename "$$file" .md); \
		cp "$$file" "man/$$name"; \
	done

docs: man ## Build CLI docs artifacts
	@echo "CLI docs and man sources are ready."

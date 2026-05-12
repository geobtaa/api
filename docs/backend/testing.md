# Testing

This document describes how to run the test suite for the application.

## Prerequisites

Ensure you have the development dependencies installed. You can install them along with the package in editable mode using `uv`:

```bash
uv pip install -e '.[dev]'
```

## Running the Full Test Suite

To run all tests, including linting with Ruff, code coverage with pytest-cov, and the pytest suite itself, you can use the provided Makefile:

```bash
make lint-test
```

This command will:
1. Check code formatting and linting with Ruff
2. Run the pytest suite with coverage reporting

## Code Quality Tools

The project uses Ruff for both linting and formatting:

### Linting

To check your code for issues without modifying files:

```bash
make lint
```

This runs Ruff's check command on the codebase.

### Formatting

To automatically format your code:

```bash
make format
```

This runs Ruff's format command and then applies any auto-fixes from the linter.

### Format Checking (CI)

To check if code is properly formatted without modifying files (useful for CI):

```bash
make lint-check
```

## Running Tests

You can run the test suite using:

```bash
make test
```

This runs pytest (optionally in parallel) with a **wall-clock timeout** so the suite can’t hang forever.

- **Default timeout**: 180 seconds (3 minutes) for the entire run
- **Override**:
  - `WALLCLOCK_TIMEOUT_SECONDS=0 make test` (disable timeout; debug only)
  - `WALLCLOCK_TIMEOUT_SECONDS=900 make test` (15 minutes)

## Running Individual Tests

Run targeted tests from `backend/` with Python's pytest module, or from the
repository root with the Makefile for standard full-suite behavior.

```bash
cd backend
python -m pytest tests/api/v1/test_search_endpoints.py
python -m pytest tests/services/ -k search
python -m pytest -m <marker_name>
```

If Docker services are required for the test you are running, start them first:

```bash
docker compose up -d paradedb elasticsearch redis
```

## Test Coverage

`make test` runs pytest with coverage and enforces `COVERAGE_THRESHOLD`
(default `50`). `make test-no-coverage` and `make test-fast` skip coverage for
debugging speed. HTML coverage output is written under `backend/htmlcov/` when
coverage is enabled.

## Quarterly Test Maintenance

- Re-run the full backend suite with `make test`.
- Review slow or flaky tests and update timeout/concurrency guidance if needed.
- Confirm Docker test database setup still matches the Makefile.
- Add regression tests for any production incidents or runbook changes from the
  quarter.
- Keep this file and [../make_tasks.md](../make_tasks.md) aligned with new test
  targets or environment variables.

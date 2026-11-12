# Testing

This document describes how to run the test suite for the application.

## Interactive Documentation Examples

The example tests execute the visible Python snippets with mock responses
during ordinary CI. To check them against a running local API with catalog data,
run from the repository root:

```bash
BTAA_SKIP_TEST_DB=true MKDOCS_EXAMPLES_BASE_URL=http://localhost:8000 \
  python -m pytest backend/tests/integration/test_mkdocs_interactive_examples.py -q -ra
```

The live suite checks each referenced example record once before making dependent
requests. `test_mkdocs_example_records_exist` reports missing records by ID and
URL; dependent examples are skipped while unrelated endpoint checks continue.
Connection, access, and server failures remain failures of the prerequisite
check. A missing subendpoint on an existing record still fails its example test.

When replacing an example record, update both the visible Python snippet and
the executable PyScript block in `mkdocs/docs/includes/examples/`. Choose a
record supporting the illustrated capabilities, including viewer data and
downloads, and validate the examples against the intended catalog. The record
ID comes directly from the snippets; no environment-variable override is applied.

The same suite includes gallery thumbnail and resource-page checks that need
their own catalog data. Live verification scheduling and access setup are covered
by the restricted operations documentation; see [Deployment](deployment.md).

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

For tests that do not need the database, set `BTAA_SKIP_TEST_DB=true` to skip
database preparation, connections, and transactions. Test configuration prepares
database URLs without creating an engine or loading its selected driver during
collection. Tests that import application database modules may still require
their usual database dependencies.

## Reliability Regression Checks

Reliability fixes should preserve intentional fallbacks while making unexpected
failures diagnosable. Catch the expected parsing or I/O exceptions, explain why
an ignored error is safe, and keep cancellation and shutdown exceptions visible.
Cleanup failures should not replace the original error.

Library imports should not print CLI diagnostics or configure file logging.
The import-isolation tests run modules in fresh processes to verify this.
From `backend/`, run the focused import and importer checks without a database:

```bash
BTAA_SKIP_TEST_DB=true python -m pytest --no-cov tests/test_import_silence.py tests/gazetteer/test_wof_importer.py tests/services/test_bridge_sync_client.py
```

Skipping database preparation does not mock database or Redis calls inside a
test. Tests that directly use those services still require them to be running.

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

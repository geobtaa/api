# Testing the BTAA QGIS Plugin

This documentation describes how to run and write tests for the BTAA QGIS Plugin. The testing strategy relies on `pytest`, `pytest-cov`, and `pytest-mock`, along with `ruff` for code formatting and linting. This matches the testing patterns used in the backend FastAPI application.

## Prerequisites

Before running the tests, ensure you have installed the testing dependencies on your environment. You can install them with `pip` via the `pyproject.toml` file.

```bash
cd qgis-plugin
python -m pip install -e ".[dev]"
```

## Running the Test Suite

We use a `Makefile` to simplify running tests and linters. It mirrors the commands in the `backend/` directory.

### Quick Commands

Make sure you are in the `qgis-plugin` directory:

- **Run tests with coverage check:**
  ```bash
  make test
  ```
  This runs `pytest` and generates both a terminal coverage report and an HTML coverage report (in `coverage_html_report/`). The tests will fail if line coverage is below 50% (default).

- **Run tests without coverage check (debugging):**
  ```bash
  make test-no-coverage
  ```
  This runs `pytest -v` without any coverage constraints, showing detailed output for each test.

- **Check formatting and linting:**
  ```bash
  make lint
  ```
  Runs `ruff check .` to highlight linting errors.

- **Fix formatting automatically:**
  ```bash
  make format
  ```
  Runs `ruff format .` followed by `ruff check --fix .`. Code should generally be formatted before making commits.

- **Check formatting for CI:**
  ```bash
  make lint-check
  ```
  Runs in CI checking mode. Fails if formatting is incorrect.

## Writing Tests

The test suite is located in the `tests/` directory.

Because QGIS plugins rely heavily on `qgis` and `PyQt` components that require a running QGIS instance, we utilize `unittest.mock` to mock these modules in `tests/conftest.py`. This allows the tests to run quickly as standard Python tests without spinning up the QGIS application locally.

When writing tests:

- Use standard `pytest` fixtures for common setup.
- Any new QGIS or PyQt modules imported by your source files must be added to the mocks in `tests/conftest.py` if they are not already.
- Store unit tests in files starting with `test_` within the `tests/` directory.
- Patch side effects, like network calls via `requests`, using python's `unittest.mock.patch`.

# Testing the BTAA Geoportal API

This directory contains tests for the BTAA Geoportal API. The tests are organized by component and use pytest as the test runner.

## Test Structure

- `tests/api/v1/`: Tests for the API v1 endpoints
- `tests/elasticsearch/`: Tests for Elasticsearch integration
- `tests/services/`: Tests for service classes
- `tests/gazetteer/`: Tests for gazetteer components
- `tests/viewers/`: Tests for viewer components

## Running Tests

To run all tests:

```bash
make test
```

To run specific tests:

```bash
# Run a specific test file
pytest tests/api/v1/test_resource_endpoints.py -v

# Run a specific test function
pytest tests/api/v1/test_resource_endpoints.py::test_get_resource -v

# Run tests with a specific marker
pytest -m "asyncio" -v
```

### Parallel Execution

The test suite supports parallel execution using `pytest-xdist` for significantly faster test runs:

```bash
# Run tests in parallel (auto-detects CPU cores)
pytest -n auto

# Run tests with a specific number of workers
pytest -n 4

# Run only fast unit tests in parallel
pytest -n auto -m unit
```

**Performance**: Parallel execution can reduce test suite runtime from ~10 minutes to 1-2 minutes on multi-core machines.

### Test Markers

Tests are categorized using pytest markers for selective execution:

- `@pytest.mark.unit` - Fast unit tests that don't require external services
- `@pytest.mark.integration` - Integration tests that require database/elasticsearch/redis
- `@pytest.mark.slow` - Tests that take a long time to run (>1 second)
- `@pytest.mark.elasticsearch` - Tests that require Elasticsearch
- `@pytest.mark.database` - Tests that require database connections
- `@pytest.mark.redis` - Tests that require Redis

**Examples**:

```bash
# Run only fast unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run tests excluding slow ones
pytest -m "not slow"

# Run database tests only
pytest -m database
```

## Test Configuration

The tests use fixtures defined in `conftest.py` files. These fixtures provide mock objects and data for testing.

### Key Fixtures

- `client`: A FastAPI test client
- `mock_document`: A mock document for testing
- `mock_elasticsearch_response`: A mock Elasticsearch response
- `mock_task`: A mock Celery task
- `db_connection`: Session-scoped database connection (reused across tests)
- `db_transaction`: Function-scoped transaction fixture for test isolation
- `es_client_session`: Session-scoped Elasticsearch client and index
- `clean_es_index`: Function-scoped fixture that clears ES documents between tests

## Testing Approach

The tests are designed to be:

1. **Isolated**: Tests should not depend on each other or external services
2. **Fast**: Tests should run quickly to enable rapid feedback
3. **Clear**: Tests should clearly show what they're testing and what the expected outcome is

### Performance Optimizations

The test suite has been optimized for speed:

1. **Session-Scoped Connections**: Database and Elasticsearch connections are created once per test session and reused, eliminating connection overhead
2. **Transaction Isolation**: Database transactions are used to ensure test isolation while allowing parallel execution
3. **Index Reuse**: Elasticsearch indices are created once per session; only documents are cleared between tests
4. **Parallel Execution**: Tests can run in parallel using `pytest-xdist` for 4-8x speedup
5. **Optional Coverage**: Coverage collection is optional (use `--cov` flag) to avoid overhead during development

### Test Isolation

- **Database**: Uses session-scoped connections with function-scoped transaction management
- **Elasticsearch**: Session-scoped index creation with function-scoped document clearing
- **Parallel Execution**: Each pytest-xdist worker process gets its own database connection, providing natural isolation

## Mock Data

Mock data for tests is defined in:

- Fixture files in `tests/fixtures/`
- Pytest fixtures in `conftest.py` files

## Adding New Tests

When adding new tests:

1. Create a new test file in the appropriate directory
2. Use existing fixtures when possible
3. Add new fixtures in the appropriate `conftest.py` file if needed
4. Follow the existing naming conventions

## Test Coverage

To generate a test coverage report:

```bash
# Run tests with coverage (slower, but provides coverage data)
pytest --cov=app --cov-report=term-missing --cov-report=html

# Or use the make target
make coverage
```

The report will be available in the `coverage_html_report` directory.

**Note**: Coverage collection adds 20-40% overhead. For faster local development, run tests without coverage and only enable it in CI or when explicitly needed. 
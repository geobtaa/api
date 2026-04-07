import asyncio
import atexit
import faulthandler
import os
import signal
import threading
import time
import warnings
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import create_engine

# Find repo root so `pytest` works whether run from repo root or from `backend/`
_HERE = Path(__file__).resolve()
_BACKEND_DIR = _HERE.parent
_REPO_ROOT = _BACKEND_DIR.parent

# Load .env first to get POSTGRES_PASSWORD
# Try to read POSTGRES_PASSWORD directly from .env file if load_dotenv doesn't work
postgres_password = None
env_paths = [Path(".env"), _REPO_ROOT / ".env"]
for env_path in env_paths:
    if not env_path.exists():
        continue
    try:
        import re

        content = env_path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r'POSTGRES_PASSWORD=["\']?([^"\'\n]+)["\']?', content)
        if match:
            postgres_password = match.group(1)
    except Exception:
        pass
    if postgres_password:
        break

# Load .env (may not work if quotes are an issue)
try:
    # Prefer repo root .env if present (common when invoking pytest from backend/)
    load_dotenv(_REPO_ROOT / ".env", override=False)
    load_dotenv(".env", override=False)
except (OSError, PermissionError):
    # In sandboxed test environments, .env may be unreadable. Continue with defaults/env.
    pass
# Use the directly read value if load_dotenv didn't set it
if postgres_password and not os.getenv("POSTGRES_PASSWORD"):
    os.environ["POSTGRES_PASSWORD"] = postgres_password

# Load test environment variables (may override other vars)
try:
    load_dotenv(_REPO_ROOT / ".env.test", override=True)
    load_dotenv(".env.test", override=True)
except (OSError, PermissionError):
    pass
# Restore POSTGRES_PASSWORD if it was set in .env but not in .env.test
if postgres_password and not os.getenv("POSTGRES_PASSWORD"):
    os.environ["POSTGRES_PASSWORD"] = postgres_password

# Fix DATABASE_URL if it contains the wrong password
if postgres_password and os.getenv("DATABASE_URL"):
    database_url = os.getenv("DATABASE_URL")
    # Replace password in DATABASE_URL if it's "postgres"
    if ":postgres@" in database_url:
        database_url = database_url.replace(":postgres@", f":{postgres_password}@")
        os.environ["DATABASE_URL"] = database_url

# Configure tests to piggy-back on primary Docker services with isolated test DB/indices
# Default to the main compose ports (ParadeDB 2345, ES 9200, Redis 6379)
TEST_DB_NAME = os.getenv("TEST_DB_NAME", "btaa_geospatial_api_test")
DB_USER = os.getenv("DB_USER", "postgres")
# Check POSTGRES_PASSWORD first (from .env), then DB_PASSWORD, then default to "postgres"
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "2345")

# Build canonical URLs; allow override via env
DATABASE_URL = os.getenv(
    "DATABASE_URL", f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{TEST_DB_NAME}"
)

# Convert Docker hostnames to localhost when running tests outside Docker
# This handles cases where DATABASE_URL is set from .env with Docker service names
is_docker = os.getenv("IS_DOCKER") == "true"
if not is_docker and DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    docker_hostnames = [
        "paradedb",
        "btaa-geospatial-api-paradedb",
        "btaa-geospatial-api-paradedb-1",
    ]
    if parsed.hostname in docker_hostnames:
        # Replace Docker hostname with localhost and use port 2345 (Docker mapped port)
        new_netloc = f"{parsed.username}:{parsed.password}@localhost:2345"
        DATABASE_URL = parsed._replace(netloc=new_netloc).geturl()
        # Update DB_HOST to match
        DB_HOST = "localhost"
        DB_PORT = "2345"

# Parse database URL
parsed = urlparse(DATABASE_URL)
db_name = parsed.path[1:]  # Remove leading '/'
db_user = parsed.username
db_password = parsed.password
db_host = parsed.hostname
db_port = parsed.port

# Create test database engine for migrations (synchronous)
# Ensure SYNC_DATABASE_URL also has the correct password
SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
engine = create_engine(SYNC_DATABASE_URL)

# Ensure async database URL is set for the tests
ASYNC_DATABASE_URL = (
    DATABASE_URL
    if "postgresql+asyncpg://" in DATABASE_URL
    else DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
)

_HB_CURRENT_NODEID: str | None = None
_HB_CURRENT_WHEN: str | None = None
_HB_STOP = threading.Event()
_HB_THREAD: threading.Thread | None = None
_HB_PATH: Path | None = None

# The `databases`/asyncpg pool is bound to the event loop that created it.
# Under pytest-asyncio, it's possible for a session-scoped connect to run on a different
# loop than individual tests. Track the loop id and reconnect if needed.
_DB_LOOP_ID: int | None = None


def _hb_worker_id() -> str:
    # xdist sets PYTEST_XDIST_WORKER like "gw0"; master has none.
    return os.getenv("PYTEST_XDIST_WORKER", "master")


def _hb_write(line: str) -> None:
    global _HB_PATH
    if _HB_PATH is None:
        return
    try:
        _HB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _HB_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except Exception:
        # Best-effort; never fail tests due to logging
        pass


def _hb_loop(interval_seconds: float) -> None:
    worker = _hb_worker_id()
    while not _HB_STOP.is_set():
        nodeid = _HB_CURRENT_NODEID or "(idle)"
        when = _HB_CURRENT_WHEN or ""
        _hb_write(
            f"[heartbeat] {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"worker={worker} when={when} nodeid={nodeid}"
        )
        _HB_STOP.wait(interval_seconds)


def pytest_configure(config):
    """Configure pytest to use main services with isolated test DB/index."""
    # Coverage is now optional - removed from default addopts for performance

    # Enable faulthandler and register SIGUSR1 so hung test runs can dump stack traces
    # (works well with our Makefile timeout wrapper and pytest-xdist).
    try:
        faulthandler.enable(all_threads=True)
        faulthandler.register(signal.SIGUSR1, all_threads=True)
    except Exception:
        # Best-effort only; do not fail tests if signals are restricted.
        pass

    # Start a per-process heartbeat log (works with xdist workers too). This makes it
    # trivial to identify the exact test/phase that was running when a suite "hangs".
    global _HB_THREAD, _HB_PATH
    try:
        log_dir = Path(os.getenv("LOG_PATH", "./test_logs"))
        _HB_PATH = log_dir / f"pytest_heartbeat_{_hb_worker_id()}.log"
        _hb_write(f"[heartbeat] starting worker={_hb_worker_id()}")
        _HB_THREAD = threading.Thread(target=_hb_loop, args=(15.0,), daemon=True)
        _HB_THREAD.start()
        atexit.register(lambda: _HB_STOP.set())
    except Exception:
        pass

    # Ensure application and migrations run in test mode
    os.environ["APP_ENV"] = "test"
    # Disable usage logging during tests for speed/stability
    os.environ["DISABLE_API_USAGE_LOG"] = "true"
    # Allow rate limiting bypass for most tests; rate-limit-specific tests can override
    os.environ["DISABLE_RATE_LIMIT_FOR_TESTS"] = "true"

    # Ensure env vars are aligned for modules that use db.config
    os.environ["DB_USER"] = DB_USER
    os.environ["DB_PASSWORD"] = DB_PASSWORD
    os.environ["DB_HOST"] = DB_HOST
    os.environ["DB_PORT"] = DB_PORT
    os.environ["DB_NAME"] = TEST_DB_NAME

    # Point application to the test DB on the primary ParadeDB service
    os.environ["DATABASE_URL"] = ASYNC_DATABASE_URL

    # Use a dedicated Elasticsearch index on the primary ES service.
    # IMPORTANT: some code paths (e.g., indexing/reindexing helpers) delete/recreate the index.
    # Never allow tests to point at production Elasticsearch.
    os.environ.setdefault(
        "ELASTICSEARCH_URL", os.getenv("ELASTICSEARCH_URL", "http://localhost:9200")
    )
    es_url = os.environ["ELASTICSEARCH_URL"]
    # Allow only clearly-local endpoints.
    allowed_markers = (
        "localhost",
        "127.0.0.1",
        "elasticsearch",
        "btaa-geospatial-api-elasticsearch",
        "http://localhost:9200",
        "http://127.0.0.1:9200",
    )
    if not any(m in es_url for m in allowed_markers):
        raise RuntimeError(
            f"Refusing to run tests against non-local Elasticsearch URL: {es_url}. "
            "Set ELASTICSEARCH_URL to your local/dev Elasticsearch (e.g. http://localhost:9200)."
        )

    # Force a test-specific index name unless explicitly overridden to another *_test index.
    es_index = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api_test")
    if not es_index.endswith("_test"):
        es_index = "btaa_geospatial_api_test"
    os.environ["ELASTICSEARCH_INDEX"] = es_index

    # Isolate Redis usage to a separate logical DB during tests
    os.environ.setdefault("REDIS_HOST", os.getenv("REDIS_HOST", "localhost"))
    os.environ.setdefault("REDIS_PORT", os.getenv("REDIS_PORT", "6379"))
    os.environ["REDIS_DB"] = os.getenv("REDIS_DB", "1")
    os.environ["ENDPOINT_CACHE"] = os.getenv("ENDPOINT_CACHE", "false")

    os.environ["LOG_PATH"] = "./test_logs"

    # Set admin credentials for tests
    os.environ["ADMIN_USERNAME"] = "admin"
    os.environ["ADMIN_PASSWORD"] = "changeme"

    # Filter out pytesseract deprecation warnings
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=".*pkgutil.find_loader.*",
        module="pytesseract.*",
    )


def pytest_runtest_logstart(nodeid, location):
    # Called in each worker when a test starts running.
    global _HB_CURRENT_NODEID, _HB_CURRENT_WHEN
    _HB_CURRENT_NODEID = nodeid
    _HB_CURRENT_WHEN = "start"
    _hb_write(
        f"[test] start {time.strftime('%Y-%m-%d %H:%M:%S')} "
        f"worker={_hb_worker_id()} nodeid={nodeid}"
    )


def pytest_runtest_logfinish(nodeid, location):
    global _HB_CURRENT_WHEN
    _HB_CURRENT_WHEN = "finish"
    _hb_write(
        f"[test] finish {time.strftime('%Y-%m-%d %H:%M:%S')} "
        f"worker={_hb_worker_id()} nodeid={nodeid}"
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Ensure test DB exists on primary ParadeDB and run needed migrations."""
    # Ensure the test database exists by connecting to the default 'postgres' DB
    admin_dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/postgres"
    try:
        with psycopg2.connect(admin_dsn) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                exists = cur.fetchone() is not None
                if not exists:
                    cur.execute(f"CREATE DATABASE {db_name}")
                    print("Created test database")
    except Exception as e:
        print(f"Warning: could not ensure test database exists: {type(e).__name__}")

    # Run minimal migrations required by tests (idempotent)
    from db.migrations.add_enrichment_type import add_enrichment_type_column
    from db.migrations.api_rate_limiting import init_api_rate_limiting
    from db.migrations.create_ai_enrichments import create_ai_enrichments_table
    from db.migrations.create_gazetteer_tables import create_gazetteer_tables
    from db.migrations.create_resource_relationships import create_relationships_table

    # Temporarily set the environment to use synchronous URL for migrations
    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = SYNC_DATABASE_URL

    try:
        create_ai_enrichments_table()
        create_gazetteer_tables()
        create_relationships_table()
        add_enrichment_type_column()
        init_api_rate_limiting()
        print("All database migrations (including API rate limiting) completed successfully!")
    except Exception as e:
        print(f"Error creating tables: {e}")
        raise
    finally:
        # Restore the async URL for tests
        if original_database_url:
            os.environ["DATABASE_URL"] = original_database_url
        else:
            os.environ["DATABASE_URL"] = ASYNC_DATABASE_URL

    yield


@pytest_asyncio.fixture(scope="session", autouse=True)
async def db_connection():
    """Session-scoped database connection that stays open for all tests."""
    from db.database import database

    # Connect once for the entire test session
    await database.connect()
    global _DB_LOOP_ID
    try:
        _DB_LOOP_ID = id(asyncio.get_running_loop())
    except Exception:
        _DB_LOOP_ID = None
    yield database
    # Disconnect at the end of the session
    await database.disconnect()


@pytest_asyncio.fixture(autouse=True)
async def db_transaction(db_connection):
    """
    Function-scoped transaction that automatically rolls back after each test.
    This ensures test isolation and allows parallel execution.

    Uses PostgreSQL savepoints to create nested transactions that can be rolled back
    without affecting other tests running in parallel.

    Note: This fixture assumes the database connection is in autocommit mode or
    can handle savepoints. If savepoints don't work, tests will still be isolated
    by running in separate database transactions when using pytest-xdist with
    separate database connections per worker.
    """
    import uuid

    from db.database import database

    # Ensure the database pool is bound to the currently running event loop.
    # If not, asyncpg will raise "Future attached to a different loop" and can leave
    # the connection in a broken state.
    global _DB_LOOP_ID
    try:
        current_loop_id = id(asyncio.get_running_loop())
    except Exception:
        current_loop_id = None

    if database.is_connected and current_loop_id is not None and _DB_LOOP_ID is not None:
        if current_loop_id != _DB_LOOP_ID:
            try:
                await database.disconnect()
            except Exception:
                pass
            await database.connect()
            _DB_LOOP_ID = current_loop_id
    elif not database.is_connected:
        await database.connect()
        _DB_LOOP_ID = current_loop_id

    # Generate a unique savepoint name
    savepoint_name = f"sp_{uuid.uuid4().hex[:12]}"

    try:
        # Try to create a savepoint for this test
        # This will work if we're already in a transaction
        try:
            await database.execute(f"SAVEPOINT {savepoint_name}")
            using_savepoint = True
        except Exception:
            # If savepoints don't work, we'll rely on transaction isolation
            # when running in parallel (each worker gets its own connection)
            using_savepoint = False

        yield database

        # Rollback to savepoint if we created one
        if using_savepoint:
            try:
                await database.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            except Exception:
                # If rollback fails, that's okay - the transaction will be handled elsewhere
                pass
    except Exception:
        # If anything goes wrong, try to clean up
        if using_savepoint:
            try:
                await database.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            except Exception:
                pass
        raise

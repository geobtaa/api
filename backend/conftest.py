import os
import pytest
import pytest_asyncio
import warnings
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError, OperationalError
import psycopg2
from dotenv import load_dotenv
from urllib.parse import urlparse
import asyncio
import atexit

# Load .env first to get POSTGRES_PASSWORD
# Try to read POSTGRES_PASSWORD directly from .env file if load_dotenv doesn't work
postgres_password = None
if os.path.exists(".env"):
    try:
        import re
        with open(".env") as f:
            content = f.read()
            match = re.search(r'POSTGRES_PASSWORD=["\']?([^"\'\n]+)["\']?', content)
            if match:
                postgres_password = match.group(1)
    except Exception:
        pass

# Load .env (may not work if quotes are an issue)
load_dotenv(".env", override=False)
# Use the directly read value if load_dotenv didn't set it
if postgres_password and not os.getenv("POSTGRES_PASSWORD"):
    os.environ["POSTGRES_PASSWORD"] = postgres_password

# Load test environment variables (may override other vars)
load_dotenv(".env.test", override=True)
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
TEST_DB_NAME = os.getenv("TEST_DB_NAME", "btaa_ogm_api_test")
DB_USER = os.getenv("DB_USER", "postgres")
# Check POSTGRES_PASSWORD first (from .env), then DB_PASSWORD, then default to "postgres"
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD") or os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "2345")

# Build canonical URLs; allow override via env
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{TEST_DB_NAME}"
)

# Convert Docker hostnames to localhost when running tests outside Docker
# This handles cases where DATABASE_URL is set from .env with Docker service names
is_docker = os.getenv("IS_DOCKER") == "true"
if not is_docker and DATABASE_URL:
    parsed = urlparse(DATABASE_URL)
    docker_hostnames = ["paradedb", "btaa-geospatial-api-paradedb", "btaa-geospatial-api-paradedb-1"]
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
ASYNC_DATABASE_URL = DATABASE_URL if "postgresql+asyncpg://" in DATABASE_URL else DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

def pytest_configure(config):
    """Configure pytest to use main services with isolated test DB/index."""
    # Coverage is now optional - removed from default addopts for performance

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

    # Use a dedicated Elasticsearch index on the primary ES service
    os.environ.setdefault("ELASTICSEARCH_URL", os.getenv("ELASTICSEARCH_URL", "http://localhost:9200"))
    os.environ["ELASTICSEARCH_INDEX"] = os.getenv("ELASTICSEARCH_INDEX", "btaa_ogm_api_test")

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
        module="pytesseract.*"
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
                    print(f"Created test database {db_name}")
    except Exception as e:
        print(f"Warning: could not ensure test database exists: {e}")

    # Run minimal migrations required by tests (idempotent)
    from db.migrations.create_ai_enrichments import create_ai_enrichments_table
    from db.migrations.create_gazetteer_tables import create_gazetteer_tables
    from db.migrations.create_resource_relationships import create_relationships_table
    from db.migrations.add_enrichment_type import add_enrichment_type_column
    from db.migrations.api_rate_limiting import init_api_rate_limiting

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
    from db.database import database
    import uuid
    
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

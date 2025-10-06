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

# Load test environment variables
load_dotenv(".env.test", override=True)

# Configure tests to piggy-back on primary Docker services with isolated test DB/indices
# Default to the main compose ports (ParadeDB 2345, ES 9200, Redis 6379)
TEST_DB_NAME = os.getenv("TEST_DB_NAME", "btaa_ogm_api_test")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "2345")

# Build canonical URLs; allow override via env
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{TEST_DB_NAME}"
)

# Parse database URL
parsed = urlparse(DATABASE_URL)
db_name = parsed.path[1:]  # Remove leading '/'
db_user = parsed.username
db_password = parsed.password
db_host = parsed.hostname
db_port = parsed.port

# Create test database engine for migrations (synchronous)
SYNC_DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
engine = create_engine(SYNC_DATABASE_URL)

# Ensure async database URL is set for the tests
ASYNC_DATABASE_URL = DATABASE_URL if "postgresql+asyncpg://" in DATABASE_URL else DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

def pytest_configure(config):
    """Configure pytest to use main services with isolated test DB/index."""
    config.addinivalue_line("addopts", "--cov=app --cov-report=term-missing --cov-report=html")

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
    os.environ["ENDPOINT_CACHE"] = os.getenv("ENDPOINT_CACHE", "true")

    os.environ["LOG_PATH"] = "./test_logs"

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

    # Temporarily set the environment to use synchronous URL for migrations
    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = SYNC_DATABASE_URL

    try:
        create_ai_enrichments_table()
        create_gazetteer_tables()
        create_relationships_table()
        add_enrichment_type_column()
        print("All database migrations completed successfully!")
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

@pytest_asyncio.fixture(autouse=True)
async def setup_async_database():
    """Set up async database connection for each test."""
    from db.database import database
    
    try:
        await database.connect()
        yield
    finally:
        await database.disconnect()

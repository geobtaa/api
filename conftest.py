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

# Get test database URL from environment or use default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test"
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
    """Configure pytest."""
    config.addinivalue_line("addopts", "--cov=app --cov-report=term-missing --cov-report=html")
    
    # Set test environment variables with async database URL
    os.environ["DATABASE_URL"] = ASYNC_DATABASE_URL
    os.environ["ELASTICSEARCH_INDEX"] = "btaa_ogm_api_test"
    os.environ["LOG_PATH"] = "./test_logs"
    os.environ["ENDPOINT_CACHE"] = "true"
    
    # Filter out pytesseract deprecation warnings
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=".*pkgutil.find_loader.*",
        module="pytesseract.*"
    )

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """Set up test database tables before running tests."""
    from db.migrations.create_ai_enrichments import create_ai_enrichments_table
    from db.migrations.create_gazetteer_tables import create_gazetteer_tables
    from db.migrations.create_item_relationships import create_relationships_table
    from db.migrations.add_enrichment_type import add_enrichment_type_column
    
    # Temporarily set the environment to use synchronous URL for migrations
    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = SYNC_DATABASE_URL
    
    try:
        # Create base tables
        create_ai_enrichments_table()
        create_gazetteer_tables()
        create_relationships_table()
        
        # Add any additional columns or modifications
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

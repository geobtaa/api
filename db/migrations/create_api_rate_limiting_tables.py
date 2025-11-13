import logging
import sys
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

# Load environment variables from .env file
load_dotenv()

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from db.models import metadata

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_api_rate_limiting_tables():
    """Create the API rate limiting tables."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        
        # Convert asyncpg URL to sync URL
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Handle Docker hostnames for local development
        # If running locally and DATABASE_URL points to a Docker service, convert to localhost:2345
        parsed = urlparse(sync_database_url)
        if parsed.hostname and ("paradedb" in parsed.hostname or "btaa-geospatial-api" in parsed.hostname):
            # Replace Docker hostname with localhost and use port 2345 for local development
            # Use local database credentials from environment or defaults
            local_port = os.getenv("DB_PORT", "2345")
            local_user = os.getenv("DB_USER", "postgres")
            local_password = os.getenv("DB_PASSWORD", "postgres")
            local_db = os.getenv("DB_NAME", parsed.path.lstrip("/") if parsed.path else "btaa_geospatial_api")
            
            # Build new netloc with local credentials
            new_netloc = f"{local_user}:{local_password}@localhost:{local_port}"
            sync_database_url = urlunparse(parsed._replace(netloc=new_netloc, path=f"/{local_db}"))
            logger.info(f"Converted Docker hostname to localhost:{local_port} with local credentials")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        # Check if the tables already exist
        existing_tables = inspector.get_table_names()
        logger.info(f"Existing tables: {existing_tables}")

        # Create all tables from metadata
        metadata.create_all(engine)
        logger.info("Successfully created all API rate limiting tables from metadata.")

    except Exception as e:
        logger.error(f"Error creating API rate limiting tables: {e}")
        raise


if __name__ == "__main__":
    create_api_rate_limiting_tables()



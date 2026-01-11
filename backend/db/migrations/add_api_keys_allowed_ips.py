import logging
import sys
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

# Load environment variables with support for test environment
BASE_DIR = Path(__file__).resolve().parents[2]
APP_ENV = os.getenv("APP_ENV", "development")

if APP_ENV == "test":
    # In test mode, layer .env.test over .env
    load_dotenv(BASE_DIR / ".env", override=False)
    load_dotenv(BASE_DIR / ".env.test", override=True)
else:
    # Default: behave like original script, loading .env from project root
    load_dotenv(BASE_DIR / ".env", override=False)

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_api_keys_allowed_ips_column():
    """Add allowed_ips JSON column to api_keys table."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Handle Docker hostnames for local development (only if NOT running in Docker)
        is_docker = os.getenv("IS_DOCKER", "false").lower() == "true"
        if not is_docker:
            parsed = urlparse(sync_database_url)
            if parsed.hostname and ("paradedb" in parsed.hostname or "btaa-geospatial-api" in parsed.hostname):
                local_port = os.getenv("DB_PORT", "2345")
                local_user = os.getenv("DB_USER", "postgres")
                local_password = os.getenv("DB_PASSWORD", "postgres")
                local_db = os.getenv("DB_NAME", parsed.path.lstrip("/") if parsed.path else "btaa_geospatial_api")
                
                new_netloc = f"{local_user}:{local_password}@localhost:{local_port}"
                sync_database_url = urlunparse(parsed._replace(netloc=new_netloc, path=f"/{local_db}"))
                logger.info(f"Converted Docker hostname to localhost:{local_port} with local credentials")
        else:
            logger.info("Running in Docker, using DATABASE_URL as-is with Docker service names")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        # Check if the table exists
        if not inspector.has_table("api_keys"):
            logger.info("Table api_keys does not exist. Skipping column addition.")
            return

        # Check if the column already exists
        columns = [col["name"] for col in inspector.get_columns("api_keys")]
        if "allowed_ips" in columns:
            logger.info("Column allowed_ips already exists. Skipping addition.")
            return

        # Add the column (JSON type in PostgreSQL)
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE api_keys ADD COLUMN allowed_ips JSONB;"))
            conn.commit()
            logger.info("Successfully added allowed_ips column to api_keys table.")

    except Exception as e:
        logger.error(f"Error adding allowed_ips column: {e}")
        raise


if __name__ == "__main__":
    add_api_keys_allowed_ips_column()


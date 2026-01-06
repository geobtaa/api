"""
Migration to remove geocoding-related columns from api_usage_logs table.

This removes:
- country
- region
- city
- latitude
- longitude

These columns are being removed due to licensing complexity with geocoding databases.
"""

import logging
import os
import sys
from urllib.parse import urlparse, urlunparse

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Load environment variables (override existing env vars with .env file values)
load_dotenv(override=True)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def get_db_connection():
    """Get database connection, handling Docker hostnames for local development."""
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_geospatial_api")
    
    # Convert asyncpg URL to sync URL
    sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    # Parse the URL
    parsed = urlparse(sync_database_url)
    
    # Check if hostname is a Docker service (needs conversion to localhost)
    is_docker_hostname = parsed.hostname and ("paradedb" in parsed.hostname or "btaa-geospatial-api" in parsed.hostname)
    
    # Determine connection parameters
    # Prefer local credentials from env vars if available, otherwise use URL values
    if is_docker_hostname or os.getenv("DB_USER") or os.getenv("DB_PASSWORD"):
        # Use local database credentials from environment or defaults
        local_port = int(os.getenv("DB_PORT", str(parsed.port) if parsed.port else "2345"))
        local_user = os.getenv("DB_USER", parsed.username or "postgres")
        local_password = os.getenv("DB_PASSWORD", parsed.password or "postgres")
        local_db = os.getenv("DB_NAME", parsed.path.lstrip("/") if parsed.path else "btaa_geospatial_api")
        local_host = "localhost" if is_docker_hostname else (parsed.hostname or "localhost")
        
        logger.info(f"Connecting to: {local_user}@{local_host}:{local_port}/{local_db}")
        
        return psycopg2.connect(
            host=local_host,
            port=local_port,
            database=local_db,
            user=local_user,
            password=local_password,
        )
    
    # Use credentials directly from URL
    logger.info(f"Connecting using URL credentials: {parsed.username}@{parsed.hostname}:{parsed.port}/{parsed.path.lstrip('/')}")
    return psycopg2.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        database=parsed.path.lstrip("/") if parsed.path else "btaa_geospatial_api",
        user=parsed.username or "postgres",
        password=parsed.password or "postgres",
    )


def remove_geocoding_columns():
    """Remove geocoding columns from api_usage_logs table."""
    conn = None
    try:
        conn = get_db_connection()
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        logger.info("Removing geocoding columns from api_usage_logs table...")
        
        # Check if columns exist before dropping
        columns_to_remove = ["country", "region", "city", "latitude", "longitude"]
        
        for column in columns_to_remove:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'api_usage_logs' 
                AND column_name = %s
            """, (column,))
            
            if cursor.fetchone():
                logger.info(f"Dropping column: {column}")
                cursor.execute(f'ALTER TABLE api_usage_logs DROP COLUMN IF EXISTS "{column}"')
                logger.info(f"✓ Dropped column: {column}")
            else:
                logger.info(f"Column {column} does not exist, skipping")
        
        logger.info("✓ Successfully removed geocoding columns from api_usage_logs table")
        
        cursor.close()
        
    except Exception as e:
        logger.error(f"Error removing geocoding columns: {e}", exc_info=True)
        if conn:
            conn.rollback()
        raise
    
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    try:
        remove_geocoding_columns()
        logger.info("Migration completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


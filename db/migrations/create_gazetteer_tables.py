import logging
import sys
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from db.models import metadata

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_gazetteer_tables():
    """Create the gazetteer tables."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        # Check if the tables already exist
        existing_tables = inspector.get_table_names()
        logger.info(f"Existing tables: {existing_tables}")

        # Create all tables from metadata
        metadata.create_all(engine)
        logger.info("Successfully created all gazetteer tables from metadata.")

    except Exception as e:
        logger.error(f"Error creating gazetteer tables: {e}")
        raise


if __name__ == "__main__":
    create_gazetteer_tables()

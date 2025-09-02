import logging
import sys
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from db.models import item_relationships

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_relationships_table():
    """Create the item_relationships table."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        # Check if the table already exists
        if inspector.has_table("item_relationships"):
            logger.info("Table item_relationships already exists. Skipping creation.")
            return

        # Create the table
        item_relationships.create(engine)
        logger.info("Successfully created item_relationships table.")

    except Exception as e:
        logger.error(f"Error creating item_relationships table: {e}")
        raise


if __name__ == "__main__":
    create_relationships_table()

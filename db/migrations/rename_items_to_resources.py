import logging
import sys
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def rename_items_to_resources():
    """Rename the items table to resources."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@paradedb:5432/btaa_ogm_api")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        # Check if the items table exists
        if not inspector.has_table("items"):
            logger.info("Table 'items' does not exist. Skipping rename.")
            return

        # Check if the resources table already exists
        if inspector.has_table("resources"):
            logger.info("Table 'resources' already exists. Skipping rename.")
            return

        with engine.connect() as conn:
            # Rename the table
            conn.execute(text("ALTER TABLE items RENAME TO resources"))
            conn.commit()
            logger.info("Successfully renamed 'items' table to 'resources'.")

    except Exception as e:
        logger.error(f"Error renaming items table to resources: {e}")
        raise


if __name__ == "__main__":
    rename_items_to_resources()

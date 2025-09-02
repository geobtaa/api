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


def rename_all_item_tables():
    """Rename all item_* tables to resource_* tables."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@paradedb:5432/btaa_ogm_api")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        # Define the table renames
        table_renames = [
            ("item_ai_enrichments", "resource_ai_enrichments"),
            ("item_allmaps", "resource_allmaps"),
            ("item_relationships", "resource_relationships"),
        ]

        with engine.connect() as conn:
            for old_name, new_name in table_renames:
                # Check if the old table exists
                if not inspector.has_table(old_name):
                    logger.info(f"Table '{old_name}' does not exist. Skipping rename.")
                    continue

                # Check if the new table already exists
                if inspector.has_table(new_name):
                    logger.info(f"Table '{new_name}' already exists. Skipping rename of '{old_name}'.")
                    continue

                # Rename the table
                conn.execute(text(f"ALTER TABLE {old_name} RENAME TO {new_name}"))
                conn.commit()
                logger.info(f"Successfully renamed '{old_name}' table to '{new_name}'.")

        logger.info("All table renames completed successfully.")

    except Exception as e:
        logger.error(f"Error renaming item tables: {e}")
        raise


if __name__ == "__main__":
    rename_all_item_tables()

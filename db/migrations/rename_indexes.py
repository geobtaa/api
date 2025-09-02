import logging
import sys
import os
from pathlib import Path

from sqlalchemy import create_engine, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def rename_indexes():
    """Rename indexes that still reference old item_ naming."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@paradedb:5432/btaa_ogm_api")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)

        with engine.connect() as conn:
            # Define the index renames
            index_renames = [
                ("ix_item_allmaps_item_id", "ix_resource_allmaps_resource_id"),
            ]

            for old_name, new_name in index_renames:
                # Check if the old index exists
                result = conn.execute(text("""
                    SELECT indexname FROM pg_indexes 
                    WHERE indexname = :old_name
                """), {"old_name": old_name})
                
                if not result.fetchone():
                    logger.info(f"Index '{old_name}' does not exist. Skipping rename.")
                    continue

                # Check if the new index already exists
                result = conn.execute(text("""
                    SELECT indexname FROM pg_indexes 
                    WHERE indexname = :new_name
                """), {"new_name": new_name})
                
                if result.fetchone():
                    logger.info(f"Index '{new_name}' already exists. Skipping rename of '{old_name}'.")
                    continue

                # Rename the index
                conn.execute(text(f"ALTER INDEX {old_name} RENAME TO {new_name}"))
                conn.commit()
                logger.info(f"Successfully renamed index '{old_name}' to '{new_name}'.")

        logger.info("All index renames completed successfully.")

    except Exception as e:
        logger.error(f"Error renaming indexes: {e}")
        raise


if __name__ == "__main__":
    rename_indexes()

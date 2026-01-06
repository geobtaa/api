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


def rename_remaining_constraints():
    """Rename remaining constraints and indexes that still reference old naming."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@paradedb:5432/btaa_ogm_api")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)

        with engine.connect() as conn:
            # Define the constraint/index renames
            renames = [
                # Primary key constraints
                ("items_pkey", "resources_pkey"),
                ("item_allmaps_pkey", "resource_allmaps_pkey"),
                ("item_relationships_pkey", "resource_relationships_pkey"),
                
                # Indexes
                ("ix_item_allmaps_allmaps_id", "ix_resource_allmaps_allmaps_id"),
            ]

            for old_name, new_name in renames:
                try:
                    # Check if the old constraint/index exists
                    result = conn.execute(text("""
                        SELECT conname FROM pg_constraint 
                        WHERE conname = :old_name
                        UNION ALL
                        SELECT indexname FROM pg_indexes 
                        WHERE indexname = :old_name
                    """), {"old_name": old_name})
                    
                    if not result.fetchone():
                        logger.info(f"Constraint/Index '{old_name}' does not exist. Skipping rename.")
                        continue

                    # Check if the new name already exists
                    result = conn.execute(text("""
                        SELECT conname FROM pg_constraint 
                        WHERE conname = :new_name
                        UNION ALL
                        SELECT indexname FROM pg_indexes 
                        WHERE indexname = :new_name
                    """), {"new_name": new_name})
                    
                    if result.fetchone():
                        logger.info(f"Constraint/Index '{new_name}' already exists. Skipping rename of '{old_name}'.")
                        continue

                    # Try to rename as constraint first
                    try:
                        conn.execute(text(f"ALTER TABLE {old_name.split('_')[0]}s RENAME CONSTRAINT {old_name} TO {new_name}"))
                        logger.info(f"Successfully renamed constraint '{old_name}' to '{new_name}'.")
                    except:
                        # If that fails, try to rename as index
                        try:
                            conn.execute(text(f"ALTER INDEX {old_name} RENAME TO {new_name}"))
                            logger.info(f"Successfully renamed index '{old_name}' to '{new_name}'.")
                        except Exception as e:
                            logger.warning(f"Could not rename '{old_name}' to '{new_name}': {e}")
                            continue
                    
                    conn.commit()
                    
                except Exception as e:
                    logger.warning(f"Error processing '{old_name}': {e}")
                    continue

        logger.info("All remaining constraint/index renames completed.")

    except Exception as e:
        logger.error(f"Error renaming remaining constraints: {e}")
        raise


if __name__ == "__main__":
    rename_remaining_constraints()

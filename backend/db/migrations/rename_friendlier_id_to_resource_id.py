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


def rename_friendlier_id_to_resource_id():
    """
    Rename the friendlier_id column to resource_id in the resource_distributions table.
    
    This migration:
    1. Renames the friendlier_id column to resource_id
    2. Updates the indexes to reference the new column name
    3. Updates any constraints that reference the old column name
    """
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        logger.info("Renaming friendlier_id to resource_id in resource_distributions table...")

        with engine.connect() as conn:
            # Check if the table exists
            if not inspector.has_table("resource_distributions"):
                logger.warning("resource_distributions table does not exist. Skipping migration.")
                return

            # Check if friendlier_id column exists
            columns = inspector.get_columns("resource_distributions")
            column_names = [col['name'] for col in columns]
            
            if 'friendlier_id' not in column_names:
                if 'resource_id' in column_names:
                    logger.info("Column already renamed to resource_id. Skipping migration.")
                else:
                    logger.warning("Neither friendlier_id nor resource_id column found. Skipping migration.")
                return

            # Drop existing indexes that reference friendlier_id
            logger.info("Dropping existing indexes...")
            indexes_to_drop = [
                "idx_resource_distributions_friendlier_id",
                "idx_resource_distributions_friendlier_id_type"
            ]
            
            for index_name in indexes_to_drop:
                try:
                    conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
                    logger.info(f"Dropped index: {index_name}")
                except Exception as e:
                    logger.warning(f"Could not drop index {index_name}: {e}")

            # Rename the column
            logger.info("Renaming friendlier_id column to resource_id...")
            conn.execute(text("""
                ALTER TABLE resource_distributions 
                RENAME COLUMN friendlier_id TO resource_id
            """))
            logger.info("✓ Column renamed successfully")

            # Recreate indexes with new column name
            logger.info("Recreating indexes with new column name...")
            
            # Index on resource_id
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_distributions_resource_id 
                ON resource_distributions (resource_id);
            """))
            
            # Composite index on resource_id and distribution_type_id
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_distributions_resource_id_type 
                ON resource_distributions (resource_id, distribution_type_id);
            """))
            
            logger.info("✓ Indexes recreated successfully")

            # Commit all changes
            conn.commit()
            
            logger.info("🎉 Migration completed successfully!")
            logger.info("  - Renamed friendlier_id column to resource_id")
            logger.info("  - Updated indexes to reference resource_id")
            logger.info("  - All constraints preserved")

    except Exception as e:
        logger.error(f"Error renaming friendlier_id to resource_id: {e}")
        raise


if __name__ == "__main__":
    rename_friendlier_id_to_resource_id()

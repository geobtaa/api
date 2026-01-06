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


def rename_item_id_to_resource_id():
    """Rename item_id columns to resource_id in relevant tables."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@paradedb:5432/btaa_ogm_api")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        # Define the column renames for each table
        column_renames = [
            ("resource_allmaps", "item_id", "resource_id"),
            ("resource_ai_enrichments", "item_id", "resource_id"),
        ]

        with engine.connect() as conn:
            for table_name, old_column, new_column in column_renames:
                # Check if the table exists
                if not inspector.has_table(table_name):
                    logger.info(f"Table '{table_name}' does not exist. Skipping column rename.")
                    continue

                # Check if the old column exists
                columns = inspector.get_columns(table_name)
                column_names = [col['name'] for col in columns]
                
                if old_column not in column_names:
                    logger.info(f"Column '{old_column}' does not exist in table '{table_name}'. Skipping rename.")
                    continue

                # Check if the new column already exists
                if new_column in column_names:
                    logger.info(f"Column '{new_column}' already exists in table '{table_name}'. Skipping rename.")
                    continue

                # Rename the column
                conn.execute(text(f"ALTER TABLE {table_name} RENAME COLUMN {old_column} TO {new_column}"))
                conn.commit()
                logger.info(f"Successfully renamed column '{old_column}' to '{new_column}' in table '{table_name}'.")

        logger.info("All column renames completed successfully.")

    except Exception as e:
        logger.error(f"Error renaming item_id columns to resource_id: {e}")
        raise


if __name__ == "__main__":
    rename_item_id_to_resource_id()

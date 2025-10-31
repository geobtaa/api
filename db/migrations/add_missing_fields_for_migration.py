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


def add_missing_fields_for_migration():
    """
    Add missing fields to the resources table to support migration from old production database.
    
    These fields were identified during bridge mapping verification as existing in the
    old kithe_models.json_attributes but not in the new schema.
    """
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:2345/btaa_ogm_api")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        # Check if the table exists
        if not inspector.has_table("resources"):
            logger.error("Resources table does not exist. Cannot add fields.")
            return

        with engine.connect() as conn:
            # List of additional fields to add
            additional_fields = [
                # BTAA-specific fields found in old database
                ("b1g_adms_supportedSchema_sm", "VARCHAR[]"),
                ("b1g_dateAccessioned_sm", "VARCHAR[]"),  # Array version for migration compatibility
                ("b1g_dcat_endpointDescription_s", "VARCHAR"),
                ("b1g_dcat_endpointURL_s", "VARCHAR"),
                ("b1g_dcat_inSeries_sm", "VARCHAR[]"),
                ("b1g_localCollectionLabel_sm", "VARCHAR[]"),
                ("b1g_prov_softwareAgent_sm", "VARCHAR[]"),
                ("b1g_prov_wasGeneratedBy_sm", "VARCHAR[]"),
                ("date_created_dtsi", "TIMESTAMP"),
                ("date_modified_dtsi", "TIMESTAMP"),
                ("geomg_id_s", "VARCHAR"),
                ("publication_state", "VARCHAR"),
                ("import_id", "VARCHAR"),
            ]

            # Add each field if it doesn't exist
            for field_name, field_type in additional_fields:
                try:
                    # Try to add the column - PostgreSQL will error if it already exists
                    conn.execute(text(f"ALTER TABLE resources ADD COLUMN {field_name} {field_type}"))
                    conn.commit()
                    logger.info(f"Added column {field_name} to resources table")
                except Exception as e:
                    conn.rollback()  # Rollback on error to keep transaction clean
                    if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                        logger.info(f"Column {field_name} already exists in resources table")
                    else:
                        logger.warning(f"Could not add column {field_name}: {e}")
            logger.info("Successfully added missing fields to resources table.")

    except Exception as e:
        logger.error(f"Error adding missing fields: {e}")
        raise


if __name__ == "__main__":
    add_missing_fields_for_migration()


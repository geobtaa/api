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


def add_btaa_ogm_fields():
    """Add BTAA-specific OGM Aardvark fields to the resources table."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:2345/btaa_ogm_api")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        # Check if the table exists
        if not inspector.has_table("resources"):
            logger.error("Resources table does not exist. Cannot add BTAA fields.")
            return

        with engine.connect() as conn:
            # List of BTAA fields to add
            btaa_fields = [
                ("b1g_code_s", "VARCHAR"),
                ("b1g_status_s", "VARCHAR"),
                ("b1g_dct_accrualmethod_s", "VARCHAR"),
                ("b1g_dct_accrualperiodicity_s", "VARCHAR"),
                ("b1g_dateaccessioned_s", "DATE"),
                ("b1g_dateretired_s", "DATE"),
                ("b1g_child_record_b", "BOOLEAN"),
                ("b1g_dct_mediator_sm", "VARCHAR[]"),
                ("b1g_access_s", "JSONB"),
                ("b1g_image_ss", "VARCHAR"),
                ("b1g_geonames_sm", "VARCHAR[]"),
                ("b1g_publication_state_s", "VARCHAR"),
                ("b1g_language_sm", "VARCHAR[]"),
                ("b1g_creatorid_sm", "VARCHAR[]"),
                ("b1g_dct_conformsto_sm", "VARCHAR[]"),
                ("b1g_dcat_spatialresolutioninmeters_sm", "VARCHAR[]"),
                ("b1g_geodcat_spatialresolutionastext_sm", "VARCHAR[]"),
                ("b1g_dct_provenancestatement_sm", "VARCHAR[]"),
                ("b1g_admintags_sm", "VARCHAR[]"),
            ]

            # Add each field if it doesn't exist
            for field_name, field_type in btaa_fields:
                try:
                    # Try to add the column - PostgreSQL will error if it already exists
                    conn.execute(text(f"ALTER TABLE resources ADD COLUMN {field_name} {field_type}"))
                    logger.info(f"Added column {field_name} to resources table")
                except Exception as e:
                    if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                        logger.info(f"Column {field_name} already exists in resources table")
                    else:
                        logger.warning(f"Could not add column {field_name}: {e}")

            conn.commit()
            logger.info("Successfully added BTAA OGM fields to resources table.")

    except Exception as e:
        logger.error(f"Error adding BTAA OGM fields: {e}")
        raise


if __name__ == "__main__":
    add_btaa_ogm_fields()

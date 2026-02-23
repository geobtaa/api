import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from db.models import document_data_dictionaries, document_data_dictionary_entries, metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_data_dictionary_tables():
    """Create data dictionary tables from SQLAlchemy metadata (idempotent)."""
    try:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test",
        )
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

        engine = create_engine(sync_database_url)

        # Ensure table objects are imported and then create any missing tables/indexes.
        _ = (document_data_dictionaries, document_data_dictionary_entries)
        metadata.create_all(engine)
        logger.info("✓ Data dictionary tables ensured via metadata.create_all()")
    except Exception as e:
        logger.error("Error creating data dictionary tables: %s", e)
        raise


if __name__ == "__main__":
    create_data_dictionary_tables()

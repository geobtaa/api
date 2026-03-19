import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from db.models import metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_bridge_sync_tables():
    """Create bridge sync tables from SQLAlchemy metadata (idempotent)."""
    try:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:2345/btaa_geospatial_api_test",
        )
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        existing_tables = set(inspector.get_table_names())
        logger.info("Existing tables count: %s", len(existing_tables))

        metadata.create_all(engine)
        logger.info("✓ Bridge sync tables ensured via metadata.create_all()")
    except Exception as exc:
        logger.error("Error creating bridge sync tables: %s", exc)
        raise


if __name__ == "__main__":
    create_bridge_sync_tables()

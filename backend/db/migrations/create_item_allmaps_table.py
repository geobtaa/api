"""Ensure the legacy item/resource allmaps table exists.

This helper keeps the old function name for compatibility with
`scripts/run_migrations.py`, but it now creates the current
`resource_allmaps` table when needed.
"""

import logging
import sys
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy import create_engine

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from db.config import DATABASE_URL
from db.models import resource_allmaps

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_item_allmaps_table():
    """Create the current allmaps table if neither legacy nor current table exists."""
    try:
        sync_database_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        if inspector.has_table("resource_allmaps"):
            logger.info("Table resource_allmaps already exists. Skipping creation.")
            return

        if inspector.has_table("item_allmaps"):
            logger.info("Table item_allmaps already exists. Skipping creation.")
            return

        resource_allmaps.create(engine)
        logger.info("Successfully created resource_allmaps table.")
    except Exception as e:
        logger.error(f"Error creating allmaps table: {e}")
        raise


if __name__ == "__main__":
    create_item_allmaps_table()

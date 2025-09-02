import logging
import sys
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from db.models import resource_ai_enrichments as ai_enrichments

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_ai_enrichments_table():
    """Create the resource_ai_enrichments table."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        # Check if the table already exists (handle legacy and new names)
        if inspector.has_table("resource_ai_enrichments") or inspector.has_table("item_ai_enrichments"):
            logger.info("AI enrichments table already exists. Skipping creation.")
            return

        with engine.connect() as conn:
            # Drop the index if it exists
            conn.execute(text("DROP INDEX IF EXISTS ix_ai_enrichments_document_id;"))
            conn.commit()

            # Create the table
            ai_enrichments.create(engine)
            logger.info("Successfully created resource_ai_enrichments table.")

    except Exception as e:
        logger.error(f"Error creating ai_enrichments table: {e}")
        raise


if __name__ == "__main__":
    create_ai_enrichments_table()

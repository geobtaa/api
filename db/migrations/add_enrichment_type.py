import logging
import sys
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Add debug information
print("Python path:", sys.path)
print("Current working directory:", os.getcwd())
print("Virtual environment:", os.environ.get("VIRTUAL_ENV"))

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_enrichment_type_column():
    """Add enrichment_type column to ai_enrichments table."""
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        # Check if the table exists
        if not inspector.has_table("item_ai_enrichments"):
            logger.info("Table item_ai_enrichments does not exist. Skipping column addition.")
            return

        # Check if the column already exists
        columns = [col["name"] for col in inspector.get_columns("item_ai_enrichments")]
        if "enrichment_type" in columns:
            logger.info("Column enrichment_type already exists. Skipping addition.")
            return

        # Add the column
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE item_ai_enrichments ADD COLUMN enrichment_type VARCHAR(50);"))
            conn.commit()
            logger.info("Successfully added enrichment_type column to item_ai_enrichments table.")

    except Exception as e:
        logger.error(f"Error adding enrichment_type column: {e}")
        raise


if __name__ == "__main__":
    add_enrichment_type_column()

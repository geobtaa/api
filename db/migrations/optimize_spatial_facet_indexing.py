import logging
import sys
import os
from pathlib import Path

from sqlalchemy import create_engine, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def optimize_spatial_facet_indexing():
    """
    Create helpful indexes to speed up spatial facet indexing:
    - Partial index on resources(id) where dcat_bbox is present
    - Composite index on (dcat_bbox, id) with same predicate for ORDER BY id
    """
    try:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test",
        )
        sync_database_url = database_url.replace(
            "postgresql+asyncpg://", "postgresql://"
        )

        engine = create_engine(sync_database_url)

        with engine.connect() as conn:
            logger.info("Creating partial index on resources(id) where dcat_bbox present...")
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_resources_dcat_bbox_not_null 
                    ON resources (id)
                    WHERE dcat_bbox IS NOT NULL AND dcat_bbox <> '';
                    """
                )
            )
            conn.commit()

        with engine.connect() as conn:
            logger.info(
                "Creating composite index on resources(dcat_bbox, id) where dcat_bbox present..."
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_resources_dcat_bbox_id 
                    ON resources (dcat_bbox, id)
                    WHERE dcat_bbox IS NOT NULL AND dcat_bbox <> '';
                    """
                )
            )
            conn.commit()

        logger.info("✓ Spatial facet indexing optimizations applied")

    except Exception as e:
        logger.error(f"Error optimizing spatial facet indexing: {e}")
        raise


if __name__ == "__main__":
    optimize_spatial_facet_indexing()



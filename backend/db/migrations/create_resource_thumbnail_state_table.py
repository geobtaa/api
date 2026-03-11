import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_resource_thumbnail_state_table():
    """Create the resource_thumbnail_state table for persisted thumbnail harvesting status."""
    try:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test",
        )
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        engine = create_engine(sync_database_url)

        logger.info("Creating resource_thumbnail_state table...")
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS resource_thumbnail_state (
                        resource_id VARCHAR(255) PRIMARY KEY,
                        state VARCHAR(32) NOT NULL,
                        source_type VARCHAR(32),
                        source_url TEXT,
                        source_host VARCHAR(255),
                        source_hash VARCHAR(64),
                        queue_task_id VARCHAR(255),
                        state_detail TEXT,
                        last_error TEXT,
                        queued_at TIMESTAMP WITH TIME ZONE,
                        succeeded_at TIMESTAMP WITH TIME ZONE,
                        failed_at TIMESTAMP WITH TIME ZONE,
                        placeheld_at TIMESTAMP WITH TIME ZONE,
                        last_transition_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                        FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
                    );
                    """
                )
            )
            conn.commit()
        logger.info("✓ Table created")

        logger.info("Creating indexes...")
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_resource_thumbnail_state_state
                    ON resource_thumbnail_state (state);
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_resource_thumbnail_state_source_type
                    ON resource_thumbnail_state (source_type);
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_resource_thumbnail_state_source_host
                    ON resource_thumbnail_state (source_host);
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_resource_thumbnail_state_source_hash
                    ON resource_thumbnail_state (source_hash);
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_resource_thumbnail_state_last_transition_at
                    ON resource_thumbnail_state (last_transition_at);
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_resource_thumbnail_state_queued_at
                    ON resource_thumbnail_state (queued_at);
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_resource_thumbnail_state_succeeded_at
                    ON resource_thumbnail_state (succeeded_at);
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_resource_thumbnail_state_failed_at
                    ON resource_thumbnail_state (failed_at);
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_resource_thumbnail_state_placeheld_at
                    ON resource_thumbnail_state (placeheld_at);
                    """
                )
            )
            conn.commit()
        logger.info("✓ Indexes created")

        logger.info("Creating update trigger...")
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    CREATE OR REPLACE FUNCTION update_resource_thumbnail_state_updated_at()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.updated_at = NOW();
                        RETURN NEW;
                    END;
                    $$ language 'plpgsql';
                    """
                )
            )
            conn.execute(
                text(
                    """
                    DROP TRIGGER IF EXISTS trigger_update_resource_thumbnail_state_updated_at
                    ON resource_thumbnail_state;
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TRIGGER trigger_update_resource_thumbnail_state_updated_at
                        BEFORE UPDATE ON resource_thumbnail_state
                        FOR EACH ROW
                        EXECUTE FUNCTION update_resource_thumbnail_state_updated_at();
                    """
                )
            )
            conn.commit()
        logger.info("✓ Update trigger created")

        logger.info("Updating table statistics...")
        with engine.connect() as conn:
            conn.execute(text("ANALYZE resource_thumbnail_state;"))
            conn.commit()
        logger.info("✓ Table statistics updated")
        logger.info("🎉 resource_thumbnail_state table created successfully!")
    except Exception as e:
        logger.error("Error creating resource_thumbnail_state table: %s", e)
        raise


if __name__ == "__main__":
    create_resource_thumbnail_state_table()

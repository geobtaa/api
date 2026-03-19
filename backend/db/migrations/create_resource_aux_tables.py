import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from db.models import (  # noqa: E402
    metadata,
    resource_assets,
    resource_downloads,
    resource_licensed_accesses,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_resource_aux_tables() -> None:
    """
    Create resource_downloads, resource_licensed_accesses, and resource_assets tables.

    This migration:
    - Ensures the three tables exist via SQLAlchemy metadata.create_all (idempotent)
    - Adds simple updated_at triggers mirroring other resource_* tables
    """
    try:
        database_url = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test",
        )
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

        engine = create_engine(sync_database_url)

        logger.info("Ensuring resource aux tables via metadata.create_all()...")
        _ = (resource_downloads, resource_licensed_accesses, resource_assets)
        metadata.create_all(engine)
        logger.info("✓ Tables ensured")

        with engine.connect() as conn:
            logger.info("Creating updated_at trigger functions and triggers...")

            conn.execute(
                text(
                    """
                CREATE OR REPLACE FUNCTION update_resource_downloads_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE 'plpgsql';
                """
                )
            )
            conn.execute(
                text(
                    """
                DROP TRIGGER IF EXISTS trigger_update_resource_downloads_updated_at
                ON resource_downloads;
                """
                )
            )
            conn.execute(
                text(
                    """
                CREATE TRIGGER trigger_update_resource_downloads_updated_at
                    BEFORE UPDATE ON resource_downloads
                    FOR EACH ROW
                    EXECUTE FUNCTION update_resource_downloads_updated_at();
                """
                )
            )

            conn.execute(
                text(
                    """
                CREATE OR REPLACE FUNCTION update_resource_licensed_accesses_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE 'plpgsql';
                """
                )
            )
            conn.execute(
                text(
                    """
                DROP TRIGGER IF EXISTS trigger_update_resource_licensed_accesses_updated_at
                ON resource_licensed_accesses;
                """
                )
            )
            conn.execute(
                text(
                    """
                CREATE TRIGGER trigger_update_resource_licensed_accesses_updated_at
                    BEFORE UPDATE ON resource_licensed_accesses
                    FOR EACH ROW
                    EXECUTE FUNCTION update_resource_licensed_accesses_updated_at();
                """
                )
            )

            conn.execute(
                text(
                    """
                CREATE OR REPLACE FUNCTION update_resource_assets_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE 'plpgsql';
                """
                )
            )
            conn.execute(
                text(
                    """
                DROP TRIGGER IF EXISTS trigger_update_resource_assets_updated_at
                ON resource_assets;
                """
                )
            )
            conn.execute(
                text(
                    """
                CREATE TRIGGER trigger_update_resource_assets_updated_at
                    BEFORE UPDATE ON resource_assets
                    FOR EACH ROW
                    EXECUTE FUNCTION update_resource_assets_updated_at();
                """
                )
            )

            logger.info("✓ Triggers created")

            logger.info("Analyzing resource aux tables...")
            conn.execute(text("ANALYZE resource_downloads;"))
            conn.execute(text("ANALYZE resource_licensed_accesses;"))
            conn.execute(text("ANALYZE resource_assets;"))
            conn.commit()
            logger.info("✓ Table statistics updated")

        logger.info("🎉 Resource aux tables ready")
    except Exception as e:  # pragma: no cover - surfaced by tests
        logger.error("Error creating resource aux tables: %s", e)
        raise


if __name__ == "__main__":
    create_resource_aux_tables()


import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.append(str(Path(__file__).parent.parent))

from db.models import generated_visual_asset_links, generated_visual_assets, metadata  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_generated_visual_assets_table() -> None:
    """Create durable storage for generated visual bytes and resource links."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test",
    )
    sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_database_url)

    logger.info("Ensuring generated_visual_assets table via metadata.create_all()...")
    _ = (generated_visual_assets, generated_visual_asset_links)
    metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION update_generated_visual_assets_updated_at()
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
                DROP TRIGGER IF EXISTS trigger_update_generated_visual_assets_updated_at
                ON generated_visual_assets;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TRIGGER trigger_update_generated_visual_assets_updated_at
                    BEFORE UPDATE ON generated_visual_assets
                    FOR EACH ROW
                    EXECUTE FUNCTION update_generated_visual_assets_updated_at();
                """
            )
        )
        conn.execute(text("ANALYZE generated_visual_assets;"))
        conn.execute(text("ANALYZE generated_visual_asset_links;"))
        conn.commit()

    logger.info("generated_visual_assets table ready")


if __name__ == "__main__":
    create_generated_visual_assets_table()

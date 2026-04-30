import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.append(str(Path(__file__).parent.parent))

from db.models import (  # noqa: E402
    generated_api_response_tags,
    generated_api_responses,
    generated_resource_representations,
    metadata,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_generated_resource_representations_table() -> None:
    """Create durable storage for generated JSON:API resource and response caches."""
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test",
    )
    sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_database_url)

    logger.info(
        "Ensuring generated_resource_representations and generated_api_responses tables..."
    )
    _ = (generated_resource_representations, generated_api_responses, generated_api_response_tags)
    metadata.create_all(engine)

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION update_generated_resource_representations_updated_at()
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
                DROP TRIGGER IF EXISTS
                    trigger_update_generated_resource_representations_updated_at
                ON generated_resource_representations;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TRIGGER trigger_update_generated_resource_representations_updated_at
                    BEFORE UPDATE ON generated_resource_representations
                    FOR EACH ROW
                    EXECUTE FUNCTION update_generated_resource_representations_updated_at();
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION update_generated_api_responses_updated_at()
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
                DROP TRIGGER IF EXISTS trigger_update_generated_api_responses_updated_at
                ON generated_api_responses;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TRIGGER trigger_update_generated_api_responses_updated_at
                    BEFORE UPDATE ON generated_api_responses
                    FOR EACH ROW
                    EXECUTE FUNCTION update_generated_api_responses_updated_at();
                """
            )
        )
        conn.execute(text("ANALYZE generated_resource_representations;"))
        conn.execute(text("ANALYZE generated_api_responses;"))
        conn.execute(text("ANALYZE generated_api_response_tags;"))
        conn.commit()

    logger.info("generated resource/API response cache tables ready")


if __name__ == "__main__":
    create_generated_resource_representations_table()

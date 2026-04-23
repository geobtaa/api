import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

# Load environment variables with support for test environment
BASE_DIR = Path(__file__).resolve().parents[2]
APP_ENV = os.getenv("APP_ENV", "development")

if APP_ENV == "test":
    load_dotenv(BASE_DIR / ".env", override=False)
    load_dotenv(BASE_DIR / ".env.test", override=True)
else:
    load_dotenv(BASE_DIR / ".env", override=False)

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OLD_TABLE_NAME = "api_usage_logs"
NEW_TABLE_NAME = "analytics_api_usage_logs"


def _get_sync_database_url() -> str:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:2345/btaa_geospatial_api",
    )
    sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    parsed = urlparse(sync_database_url)
    is_docker = os.getenv("IS_DOCKER", "false").lower() == "true"
    if not is_docker and parsed.hostname and (
        "paradedb" in parsed.hostname or "btaa-geospatial-api" in parsed.hostname
    ):
        local_port = os.getenv("DB_PORT", "2345")
        local_user = os.getenv("DB_USER", "postgres")
        local_password = os.getenv("DB_PASSWORD", "postgres")
        local_db = os.getenv(
            "DB_NAME", parsed.path.lstrip("/") if parsed.path else "btaa_geospatial_api"
        )
        new_netloc = f"{local_user}:{local_password}@localhost:{local_port}"
        sync_database_url = urlunparse(parsed._replace(netloc=new_netloc, path=f"/{local_db}"))

    return sync_database_url


def rename_api_usage_logs_to_analytics_api_usage_logs() -> bool:
    """Rename the legacy api_usage_logs table and its objects to analytics_* names."""
    engine = create_engine(_get_sync_database_url())
    inspector = inspect(engine)

    old_exists = inspector.has_table(OLD_TABLE_NAME)
    new_exists = inspector.has_table(NEW_TABLE_NAME)

    if not old_exists and not new_exists:
        logger.info(
            "Neither %s nor %s exists yet. Nothing to rename.", OLD_TABLE_NAME, NEW_TABLE_NAME
        )
        return False

    if not old_exists and new_exists:
        logger.info("Table %s already exists. Rename not needed.", NEW_TABLE_NAME)
        return False

    if old_exists and new_exists:
        old_columns = {col["name"] for col in inspector.get_columns(OLD_TABLE_NAME)}
        new_columns = [col["name"] for col in inspector.get_columns(NEW_TABLE_NAME)]
        shared_columns = [column for column in new_columns if column in old_columns]

        with engine.begin() as conn:
            old_count = conn.execute(text(f'SELECT COUNT(*) FROM "{OLD_TABLE_NAME}"')).scalar_one()
            new_count = conn.execute(text(f'SELECT COUNT(*) FROM "{NEW_TABLE_NAME}"')).scalar_one()

            if old_count == 0:
                logger.info(
                    "Dropping empty legacy table %s because %s already exists.",
                    OLD_TABLE_NAME,
                    NEW_TABLE_NAME,
                )
                conn.execute(text(f'DROP TABLE "{OLD_TABLE_NAME}" CASCADE'))
                return True

            if new_count == 0 and shared_columns:
                column_sql = ", ".join(f'"{column}"' for column in shared_columns)
                logger.info(
                    "Migrating %s rows from %s into existing %s.",
                    old_count,
                    OLD_TABLE_NAME,
                    NEW_TABLE_NAME,
                )
                conn.execute(
                    text(
                        f'INSERT INTO "{NEW_TABLE_NAME}" ({column_sql}) '
                        f'SELECT {column_sql} FROM "{OLD_TABLE_NAME}"'
                    )
                )
                max_id = conn.execute(text(f'SELECT MAX(id) FROM "{NEW_TABLE_NAME}"')).scalar()
                if max_id is not None:
                    conn.execute(
                        text(
                            "SELECT setval(pg_get_serial_sequence(:table_name, 'id'), :max_id, true)"
                        ),
                        {"table_name": NEW_TABLE_NAME, "max_id": max_id},
                    )
                conn.execute(text(f'DROP TABLE "{OLD_TABLE_NAME}" CASCADE'))
                logger.info(
                    "Dropped legacy table %s after migrating rows into %s.",
                    OLD_TABLE_NAME,
                    NEW_TABLE_NAME,
                )
                return True

        raise RuntimeError(
            f"Both {OLD_TABLE_NAME} and {NEW_TABLE_NAME} exist with live data. "
            "Manual reconciliation is required before continuing."
        )

    old_indexes = [idx["name"] for idx in inspector.get_indexes(OLD_TABLE_NAME) if idx.get("name")]
    pk_constraint_name = inspector.get_pk_constraint(OLD_TABLE_NAME).get("name")

    with engine.begin() as conn:
        sequence_name = conn.execute(
            text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
            {"table_name": OLD_TABLE_NAME},
        ).scalar()

        logger.info("Renaming table %s -> %s", OLD_TABLE_NAME, NEW_TABLE_NAME)
        conn.execute(text(f'ALTER TABLE "{OLD_TABLE_NAME}" RENAME TO "{NEW_TABLE_NAME}"'))

        if pk_constraint_name and pk_constraint_name == f"{OLD_TABLE_NAME}_pkey":
            conn.execute(
                text(
                    f'ALTER TABLE "{NEW_TABLE_NAME}" '
                    f'RENAME CONSTRAINT "{pk_constraint_name}" '
                    f'TO "{NEW_TABLE_NAME}_pkey"'
                )
            )

        if sequence_name:
            raw_sequence_name = sequence_name.split(".")[-1].strip('"')
            if raw_sequence_name == f"{OLD_TABLE_NAME}_id_seq":
                logger.info(
                    "Renaming sequence %s -> %s",
                    raw_sequence_name,
                    f"{NEW_TABLE_NAME}_id_seq",
                )
                conn.execute(
                    text(
                        f'ALTER SEQUENCE "{raw_sequence_name}" '
                        f'RENAME TO "{NEW_TABLE_NAME}_id_seq"'
                    )
                )

        for old_index_name in old_indexes:
            if not old_index_name.startswith(f"ix_{OLD_TABLE_NAME}_"):
                continue
            new_index_name = old_index_name.replace(
                f"ix_{OLD_TABLE_NAME}_", f"ix_{NEW_TABLE_NAME}_", 1
            )
            logger.info("Renaming index %s -> %s", old_index_name, new_index_name)
            conn.execute(text(f'ALTER INDEX "{old_index_name}" RENAME TO "{new_index_name}"'))

    logger.info("Successfully renamed %s to %s", OLD_TABLE_NAME, NEW_TABLE_NAME)
    return True


if __name__ == "__main__":
    rename_api_usage_logs_to_analytics_api_usage_logs()

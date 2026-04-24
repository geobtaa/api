import logging
import os
import sys
from pathlib import Path
from typing import List, Sequence, Set, Tuple
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


def _copy_select_expression(column_name: str, old_columns: Set[str]) -> str | None:
    if column_name == "partition_month":
        requested_at = _ident("requested_at") if "requested_at" in old_columns else None
        existing_partition = _ident("partition_month") if "partition_month" in old_columns else None
        derived_partition = (
            f"DATE_TRUNC('month', {requested_at})::date" if requested_at else None
        )
        if existing_partition and derived_partition:
            return f"COALESCE({existing_partition}, {derived_partition})"
        return existing_partition or derived_partition

    properties_column = _ident("properties") if "properties" in old_columns else None
    if column_name in {"client_name", "client_version", "client_channel", "client_instance"}:
        existing_column = _ident(column_name) if column_name in old_columns else None
        derived_value = None
        if properties_column:
            derived_value = f"NULLIF({properties_column}->>'{column_name}', '')"
        if existing_column and derived_value:
            return f"COALESCE(NULLIF({existing_column}, ''), {derived_value})"
        return existing_column or derived_value

    if column_name == "source_host":
        source_candidates: List[str] = []
        if "source_host" in old_columns:
            source_candidates.append(f"NULLIF({_ident('source_host')}, '')")
        if "referring_domain" in old_columns:
            source_candidates.append(f"NULLIF({_ident('referring_domain')}, '')")
        if "referrer" in old_columns:
            source_candidates.append(
                f"NULLIF(substring({_ident('referrer')} from '^[a-zA-Z]+://([^/]+)'), '')"
            )
        if properties_column:
            source_candidates.append(
                "NULLIF("
                f"substring({properties_column}->>'origin' from '^[a-zA-Z]+://([^/]+)'), ''"
                ")"
            )
        if source_candidates:
            return f"COALESCE({', '.join(source_candidates)})"
        return None

    if column_name in old_columns:
        return _ident(column_name)

    return None


def _build_copy_column_sql(
    new_columns: Sequence[str], old_columns: Set[str]
) -> Tuple[str, str]:
    mapped_columns: List[Tuple[str, str]] = []
    for column_name in new_columns:
        expression = _copy_select_expression(column_name, old_columns)
        if expression is None:
            continue
        mapped_columns.append((column_name, expression))

    insert_columns_sql = ", ".join(_ident(column_name) for column_name, _ in mapped_columns)
    select_columns_sql = ", ".join(
        f"{expression} AS {_ident(column_name)}" for column_name, expression in mapped_columns
    )
    return insert_columns_sql, select_columns_sql


def _ident(name: str) -> str:
    return f'"{name.replace(chr(34), chr(34) * 2)}"'


def _set_table_id_sequence(conn, table_name: str) -> None:
    max_id = conn.execute(text(f'SELECT MAX(id) FROM "{table_name}"')).scalar()
    if max_id is not None:
        conn.execute(
            text("SELECT setval(pg_get_serial_sequence(:table_name, 'id'), :max_id, true)"),
            {"table_name": table_name, "max_id": max_id},
        )


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
        insert_columns_sql, select_columns_sql = _build_copy_column_sql(new_columns, old_columns)

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

            if new_count == 0 and insert_columns_sql:
                logger.info(
                    "Migrating %s rows from %s into existing %s.",
                    old_count,
                    OLD_TABLE_NAME,
                    NEW_TABLE_NAME,
                )
                conn.execute(
                    text(
                        f'INSERT INTO "{NEW_TABLE_NAME}" ({insert_columns_sql}) '
                        f'SELECT {select_columns_sql} FROM "{OLD_TABLE_NAME}"'
                    )
                )
                _set_table_id_sequence(conn, NEW_TABLE_NAME)
                conn.execute(text(f'DROP TABLE "{OLD_TABLE_NAME}" CASCADE'))
                logger.info(
                    "Dropped legacy table %s after migrating rows into %s.",
                    OLD_TABLE_NAME,
                    NEW_TABLE_NAME,
                )
                return True

            merge_columns = [column for column in new_columns if column != "id"]
            merge_insert_columns_sql, merge_select_columns_sql = _build_copy_column_sql(
                merge_columns, old_columns
            )
            if merge_insert_columns_sql:
                logger.info(
                    "Merging %s legacy rows from %s into populated %s using fresh ids.",
                    old_count,
                    OLD_TABLE_NAME,
                    NEW_TABLE_NAME,
                )
                _set_table_id_sequence(conn, NEW_TABLE_NAME)
                conn.execute(
                    text(
                        f'INSERT INTO "{NEW_TABLE_NAME}" ({merge_insert_columns_sql}) '
                        f'SELECT {merge_select_columns_sql} FROM "{OLD_TABLE_NAME}"'
                    )
                )
                _set_table_id_sequence(conn, NEW_TABLE_NAME)
                conn.execute(text(f'DROP TABLE "{OLD_TABLE_NAME}" CASCADE'))
                logger.info(
                    "Dropped legacy table %s after merging rows into populated %s.",
                    OLD_TABLE_NAME,
                    NEW_TABLE_NAME,
                )
                return True

        raise RuntimeError(
            f"Unable to reconcile {OLD_TABLE_NAME} into {NEW_TABLE_NAME}. "
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

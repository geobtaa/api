import logging
import sys
import os
from pathlib import Path
import ast
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

import json

from sqlalchemy import bindparam, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import ARRAY

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_old_db_connection():
    """
    Get a connection to the old production database.

    Returns:
        sqlalchemy.engine.Engine: Database engine connected to old production DB
    """
    old_db_name = os.getenv("OLD_DB_NAME", "geoportal_production_20251030")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "2345")

    old_db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{old_db_name}"
    logger.info(f"Connecting to old production database: {old_db_name}")
    engine = create_engine(old_db_url)

    return engine


def get_new_db_connection():
    """
    Get a connection to the new production database.

    Returns:
        sqlalchemy.engine.Engine: Database engine connected to new production DB
    """
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "2345")
    db_name = os.getenv("DB_NAME", "btaa_geospatial_api")

    new_db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    logger.info(f"Connecting to new production database: {db_name}")
    engine = create_engine(new_db_url)

    return engine


def validate_materialized_view():
    """
    Verify that the materialized view exists in the old database.

    Returns:
        bool: True if view exists, False otherwise
    """
    logger.info("Validating materialized view exists...")

    try:
        engine = get_old_db_connection()

        with engine.connect() as conn:
            result = conn.execute(
                text("""
                SELECT EXISTS (
                    SELECT FROM pg_matviews 
                    WHERE matviewname = 'kithe_to_resources_bridge'
                );
            """)
            )
            exists = result.scalar()

            if not exists:
                logger.error("Materialized view 'kithe_to_resources_bridge' does not exist")
                logger.error(
                    "Please run: python db/migrations/bridge_old_production.py --create-view"
                )
                return False

            # Get count
            result = conn.execute(text("SELECT COUNT(*) FROM kithe_to_resources_bridge;"))
            count = result.scalar()
            logger.info(f"✓ Materialized view exists with {count:,} records")

            return True

    except Exception as e:
        logger.error(f"Error validating materialized view: {e}")
        return False


def get_resource_column_metadata():
    """
    Get column metadata (names and array detection) from the resources table.

    Returns:
        Tuple[List[str], Set[str]]: List of column names and set of array column names
    """
    logger.info("Getting resource table column metadata...")

    try:
        engine = get_new_db_connection()
        inspector = inspect(engine)

        if not inspector.has_table("resources"):
            logger.error("Resources table does not exist in new database")
            return [], set()

        columns = inspector.get_columns("resources")
        column_names = []
        array_columns = set()

        for col in columns:
            name = col["name"]
            column_names.append(name)
            if isinstance(col.get("type"), ARRAY):
                array_columns.add(name)

        logger.info(f"✓ Found {len(column_names)} columns, {len(array_columns)} array columns")
        return column_names, array_columns

    except Exception as e:
        logger.error(f"Error getting column metadata: {e}")
        return [], set()


def get_json_column_names():
    """
    Get column names that have JSON type in the resources table.

    Returns:
        List[str]: List of JSON column names
    """
    try:
        engine = get_new_db_connection()
        inspector = inspect(engine)

        columns = inspector.get_columns("resources")
        json_columns = []
        for col in columns:
            # Check if the column type is JSON or JSONB
            col_type = str(col["type"])
            if "JSON" in col_type.upper() or "JSONB" in col_type.upper():
                json_columns.append(col["name"])

        return json_columns

    except Exception as e:
        logger.error(f"Error getting JSON column names: {e}")
        return []


def _effective_publication_state_expr() -> str:
    """Return SQL expression for a resource's effective publication state."""
    return (
        "LOWER(COALESCE(NULLIF(\"b1g_publication_state_s\", ''), "
        "NULLIF(publication_state, ''), 'published'))"
    )


def _build_retire_update_statement(resource_columns: Set[str]):
    """Build an UPDATE statement that soft-retires resources by ID."""
    set_clauses = ["publication_state = :retired_state"]

    if "b1g_publication_state_s" in resource_columns:
        set_clauses.append('"b1g_publication_state_s" = :retired_state')
    if "b1g_dateRetired_dt" in resource_columns:
        set_clauses.append('"b1g_dateRetired_dt" = COALESCE("b1g_dateRetired_dt", :retired_at)')
    if "b1g_dateRetired_s" in resource_columns:
        set_clauses.append('"b1g_dateRetired_s" = COALESCE("b1g_dateRetired_s", :retired_date)')
    if "date_modified_dtsi" in resource_columns:
        set_clauses.append("date_modified_dtsi = :retired_at")

    return text(
        f"""
        UPDATE resources
        SET {", ".join(set_clauses)}
        WHERE id IN :ids
        """
    ).bindparams(bindparam("ids", expanding=True))


def import_data(dry_run: bool = False, batch_size: int = 1000, conflict_action: str = "skip"):
    """
    Import data from the materialized view in old database to new database.

    Args:
        dry_run: If True, only simulate the import without writing data
        batch_size: Number of records to process per batch
        conflict_action: How to handle conflicts ("skip", "update", "fail")
    """
    logger.info(
        f"Starting data import (dry_run={dry_run}, batch_size={batch_size}, conflict_action={conflict_action})..."
    )

    # Validate materialized view exists
    if not validate_materialized_view():
        return

    # Get column names and type metadata from new database
    new_columns, array_columns = get_resource_column_metadata()
    if not new_columns:
        logger.error("Cannot proceed without column names")
        return

    # Get JSON column names for handling empty strings
    json_columns = get_json_column_names()
    logger.info(f"Found {len(json_columns)} JSON columns")

    try:
        old_engine = get_old_db_connection()
        new_engine = get_new_db_connection()

        # Get total count
        with old_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM kithe_to_resources_bridge;"))
            total_count = result.scalar()

        logger.info(f"Processing {total_count:,} records in batches of {batch_size}...")

        # Process in batches
        offset = 0
        imported_count = 0
        skipped_count = 0
        error_count = 0
        errors = []

        while offset < total_count:
            # Fetch batch from old database
            logger.info(f"Fetching batch: offset={offset:,}, limit={batch_size}")

            with old_engine.connect() as old_conn:
                result = old_conn.execute(
                    text(f"""
                    SELECT * FROM kithe_to_resources_bridge
                    LIMIT {batch_size} OFFSET {offset};
                """)
                )

                batch_records = []
                for row in result:
                    record = dict(row._mapping)
                    # Convert empty strings to None for JSON columns
                    for json_col in json_columns:
                        if json_col in record and record[json_col] == "":
                            record[json_col] = None
                    batch_records.append(record)

            if not batch_records:
                break

            # Import batch to new database
            if not dry_run:
                batch_imported, batch_skipped, batch_errors = _import_batch(
                    new_engine,
                    batch_records,
                    new_columns,
                    array_columns,
                    json_columns,
                    conflict_action,
                )
                imported_count += batch_imported
                skipped_count += batch_skipped
                error_count += len(batch_errors)
                errors.extend(batch_errors)
            else:
                logger.info(f"[DRY RUN] Would import {len(batch_records)} records")

            offset += batch_size
            progress_pct = (offset / total_count) * 100 if total_count > 0 else 0
            logger.info(
                f"Progress: {min(offset, total_count):,}/{total_count:,} ({progress_pct:.1f}%)"
            )

        # Print summary
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Import Summary")
        logger.info(f"{'=' * 80}")
        logger.info(f"Total records: {total_count:,}")
        if not dry_run:
            logger.info(f"Imported: {imported_count:,}")
            logger.info(f"Skipped: {skipped_count:,}")
            logger.info(f"Errors: {error_count:,}")
        else:
            logger.info(f"[DRY RUN] Would have processed: {total_count:,}")
        logger.info(f"{'=' * 80}\n")

        # Print errors if any
        if errors:
            logger.warning(f"\nFirst 10 errors:")
            for i, error in enumerate(errors[:10]):
                logger.warning(f"  {i + 1}. {error}")
            if len(errors) > 10:
                logger.warning(f"  ... and {len(errors) - 10} more errors")

    except Exception as e:
        logger.error(f"Error during import: {e}")
        raise


def retire_missing_resources(dry_run: bool = False, batch_size: int = 1000) -> int:
    """
    Soft-retire resources that exist in the new DB but not in the old-production bridge view.

    Args:
        dry_run: If True, only simulate the retirement without writing data
        batch_size: Number of resource IDs to update per batch

    Returns:
        int: Number of resources newly marked retired
    """
    logger.info(
        "Retiring resources missing from the old-production snapshot "
        f"(dry_run={dry_run}, batch_size={batch_size})..."
    )

    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")

    if not validate_materialized_view():
        return 0

    resource_columns, _ = get_resource_column_metadata()
    if not resource_columns:
        logger.error("Cannot proceed without resource column metadata")
        return 0

    try:
        old_engine = get_old_db_connection()
        new_engine = get_new_db_connection()

        old_ids: Set[str] = set()
        with old_engine.connect() as old_conn:
            result = old_conn.execution_options(stream_results=True).execute(
                text("SELECT id FROM kithe_to_resources_bridge;")
            )
            for row in result:
                old_ids.add(str(row[0]))

        logger.info("Loaded %s resource IDs from old-production bridge view", len(old_ids))

        missing_ids_to_retire: List[str] = []
        missing_total = 0
        already_retired = 0
        state_expr = _effective_publication_state_expr()

        with new_engine.connect() as new_conn:
            result = new_conn.execution_options(stream_results=True).execute(
                text(
                    f"""
                    SELECT id, {state_expr} AS effective_publication_state
                    FROM resources
                    ORDER BY id
                    """
                )
            )
            for row in result:
                resource_id = str(row[0])
                effective_state = str(row[1] or "published").lower()

                if resource_id in old_ids:
                    continue

                missing_total += 1
                if effective_state == "retired":
                    already_retired += 1
                    continue

                missing_ids_to_retire.append(resource_id)

        logger.info(
            "Found %s resources missing from old-production bridge view "
            "(already_retired=%s, to_retire=%s)",
            missing_total,
            already_retired,
            len(missing_ids_to_retire),
        )

        if dry_run:
            logger.info("[DRY RUN] Would mark %s resources as retired", len(missing_ids_to_retire))
            return len(missing_ids_to_retire)

        if not missing_ids_to_retire:
            logger.info("No additional resources needed to be retired")
            return 0

        retired_at = datetime.utcnow()
        retired_date = retired_at.date()
        retire_stmt = _build_retire_update_statement(set(resource_columns))
        retired_count = 0

        for start in range(0, len(missing_ids_to_retire), batch_size):
            batch_ids = missing_ids_to_retire[start : start + batch_size]
            with new_engine.begin() as new_conn:
                result = new_conn.execute(
                    retire_stmt,
                    {
                        "ids": batch_ids,
                        "retired_state": "retired",
                        "retired_at": retired_at,
                        "retired_date": retired_date,
                    },
                )
                retired_count += (
                    result.rowcount
                    if getattr(result, "rowcount", None) is not None
                    else len(batch_ids)
                )

        logger.info("Marked %s resources as retired", retired_count)
        return retired_count

    except Exception as e:
        logger.error(f"Error retiring missing resources: {e}")
        raise


def _import_batch(
    engine,
    records: List[Dict],
    column_names: List[str],
    array_columns: Set[str],
    json_columns: List[str],
    conflict_action: str,
) -> tuple:
    """
    Import a batch of records to the new database.

    Args:
        engine: Database engine for new database
        records: List of record dictionaries
        column_names: List of column names in the target table
        conflict_action: How to handle conflicts

    Returns:
        Tuple of (imported_count, skipped_count, errors_list)
    """
    imported_count = 0
    skipped_count = 0
    errors = []

    # Filter records to only include columns that exist in target table
    filtered_records = []
    for record in records:
        filtered_record: Dict[str, Any] = {}
        for column in column_names:
            value = record.get(column)
            filtered_record[column] = _normalize_column_value(
                column, value, array_columns, json_columns
            )
        for column, normalized_value in filtered_record.items():
            if isinstance(normalized_value, dict):
                logger.error(
                    "Unconverted dict encountered",
                    extra={
                        "resource_id": record.get("id"),
                        "column": column,
                        "value": normalized_value,
                    },
                )
                raise ValueError(
                    f"Column '{column}' for resource '{record.get('id')}' still contains a dict"
                )
        filtered_records.append(filtered_record)

    # Quote all column names to preserve mixed-case identifiers
    quoted_columns = [f'"{col}"' for col in column_names]

    # Build INSERT statement based on conflict action
    if conflict_action == "skip":
        # Use INSERT ... ON CONFLICT DO NOTHING
        insert_sql = f"""
            INSERT INTO resources ({", ".join(quoted_columns)})
            VALUES ({", ".join([":" + col for col in column_names])})
            ON CONFLICT ("id") DO NOTHING;
        """
    elif conflict_action == "update":
        # Use INSERT ... ON CONFLICT DO UPDATE
        update_clause = ", ".join(
            [f'"{col}" = EXCLUDED."{col}"' for col in column_names if col != "id"]
        )
        insert_sql = f"""
            INSERT INTO resources ({", ".join(quoted_columns)})
            VALUES ({", ".join([":" + col for col in column_names])})
            ON CONFLICT ("id") DO UPDATE SET {update_clause};
        """
    else:  # fail
        # Use regular INSERT (will fail on conflict)
        insert_sql = f"""
            INSERT INTO resources ({", ".join(quoted_columns)})
            VALUES ({", ".join([":" + col for col in column_names])});
        """

    # Execute batch import
    try:
        with engine.connect() as conn:
            # Use execute many for better performance
            result = conn.execute(text(insert_sql), filtered_records)
            conn.commit()

            if hasattr(result, "rowcount"):
                imported_count = result.rowcount
            else:
                imported_count = len(filtered_records)

    except IntegrityError as e:
        if conflict_action == "fail":
            errors.append(f"Integrity error: {str(e)}")
        # For skip/update, individual failures are handled by DO NOTHING/UPDATE
    except Exception as e:
        errors.append(f"Error importing batch: {str(e)}")

    return imported_count, skipped_count, errors


def _normalize_array_item(item: Any) -> Any:
    """Normalize individual items destined for array columns."""
    if item is None:
        return None
    if isinstance(item, dict):
        try:
            return json.dumps(item)
        except (TypeError, ValueError):
            return str(item)
    if isinstance(item, (list, tuple)):
        flattened = [str(sub) for sub in item if sub is not None]
        return "; ".join(flattened) if flattened else None
    return item


def _normalize_column_value(
    column: str,
    value: Any,
    array_columns: Set[str],
    json_columns: List[str],
) -> Any:
    """Normalize record values before inserting into the resources table."""
    if value is None:
        return None

    if column in json_columns:
        if isinstance(value, str):
            stripped = value.strip()
            if stripped in ("", "null"):
                return None
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
        return value

    if column in array_columns:
        if isinstance(value, list):
            normalized_items = []
            for item in value:
                normalized_items.append(_normalize_array_item(item))
            return normalized_items
        if isinstance(value, tuple):
            normalized_items = []
            for item in value:
                normalized_items.append(_normalize_array_item(item))
            return normalized_items
        if isinstance(value, dict):
            try:
                return [json.dumps(value)]
            except (TypeError, ValueError):
                return [str(value)]
        if isinstance(value, str):
            stripped = value.strip()
            if stripped == "":
                return None
            # Attempt to deserialize JSON-style arrays
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(stripped)
                    if isinstance(parsed, (list, tuple)):
                        return list(parsed)
                except (ValueError, SyntaxError):
                    pass
            return [stripped]
        return [value]

    # Scalar column
    if isinstance(value, list):
        if len(value) == 0:
            return None
        if len(value) == 1:
            return value[0]
        return "; ".join(str(v) for v in value)

    if isinstance(value, tuple):
        if len(value) == 0:
            return None
        if len(value) == 1:
            return value[0]
        return "; ".join(str(v) for v in value)

    if isinstance(value, dict):
        try:
            return json.dumps(value)
        except (TypeError, ValueError):
            return str(value)

    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if "{" in stripped or "}" in stripped:
                return stripped
            try:
                parsed = ast.literal_eval(stripped)
                if isinstance(parsed, list):
                    if len(parsed) == 0:
                        return ""
                    if len(parsed) == 1:
                        return parsed[0]
                    return "; ".join(str(v) for v in parsed)
            except (ValueError, SyntaxError):
                pass
        if stripped.startswith("(") and stripped.endswith(")"):
            if "{" in stripped or "}" in stripped:
                return stripped
            try:
                parsed = ast.literal_eval(stripped)
                if isinstance(parsed, tuple):
                    if len(parsed) == 0:
                        return ""
                    if len(parsed) == 1:
                        return parsed[0]
                    return "; ".join(str(v) for v in parsed)
            except (ValueError, SyntaxError):
                pass
        return value

    return value


def verify_import():
    """
    Verify the imported data by comparing counts and sampling records.
    """
    logger.info("Verifying imported data...")

    try:
        old_engine = get_old_db_connection()
        new_engine = get_new_db_connection()

        # Get counts
        with old_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM kithe_to_resources_bridge;"))
            old_count = result.scalar()

        with new_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM resources;"))
            new_count = result.scalar()
            result = conn.execute(
                text(
                    f"""
                    SELECT COUNT(*) FROM resources
                    WHERE {_effective_publication_state_expr()} = 'published'
                    """
                )
            )
            published_count = result.scalar()

        logger.info(f"\n{'=' * 80}")
        logger.info(f"Import Verification")
        logger.info(f"{'=' * 80}")
        logger.info(f"Old database records: {old_count:,}")
        logger.info(f"New database records (all): {new_count:,}")
        logger.info(f"New database records (published): {published_count:,}")
        if published_count == old_count:
            logger.info("✓ Published resource count matches old-production bridge view")
        else:
            logger.warning(
                "Published resource count does not match old-production bridge view "
                f"(old={old_count:,}, published_new={published_count:,})"
            )

        # Sample some records for comparison
        logger.info("\nSampling records for comparison...")
        with old_engine.connect() as conn:
            result = conn.execute(
                text("SELECT id, dct_title_s FROM kithe_to_resources_bridge LIMIT 10;")
            )
            old_samples = [(row[0], row[1]) for row in result]

        with new_engine.connect() as conn:
            # Build a WHERE clause for the sampled IDs
            ids = [sample[0] for sample in old_samples]
            placeholders = ", ".join([f"'{id}'" for id in ids])
            result = conn.execute(
                text(f"SELECT id, dct_title_s FROM resources WHERE id IN ({placeholders});")
            )
            new_samples = {(row[0], row[1]) for row in result}

        # Compare
        matching = 0
        for old_sample in old_samples:
            if old_sample in new_samples:
                matching += 1

        logger.info(f"Sample comparison: {matching}/{len(old_samples)} records match")

        if matching == len(old_samples):
            logger.info("✓ All sampled records imported successfully")
        else:
            logger.warning(f"⚠ Only {matching}/{len(old_samples)} sampled records found")

        logger.info(f"{'=' * 80}\n")

    except Exception as e:
        logger.error(f"Error verifying import: {e}")
        raise


def main():
    """
    Main entry point for the import script.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Import data from old production database")
    parser.add_argument(
        "--dry-run", action="store_true", help="Simulate import without writing data"
    )
    parser.add_argument(
        "--batch-size", type=int, default=1000, help="Number of records per batch (default: 1000)"
    )
    parser.add_argument(
        "--conflict",
        choices=["skip", "update", "fail"],
        default="skip",
        help="How to handle ID conflicts: skip, update, or fail (default: skip)",
    )
    parser.add_argument(
        "--retire-missing",
        action="store_true",
        help="Mark resources missing from the old-production bridge view as retired",
    )
    parser.add_argument("--verify", action="store_true", help="Verify the import after running")

    args = parser.parse_args()

    # Run import
    import_data(dry_run=args.dry_run, batch_size=args.batch_size, conflict_action=args.conflict)

    if args.retire_missing:
        retire_missing_resources(dry_run=args.dry_run, batch_size=args.batch_size)

    # Verify if requested
    if args.verify and not args.dry_run:
        verify_import()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Migrate legacy document_distributions into resource_distributions.

This script copies rows from the legacy `document_distributions` table in the old
Geoportal database into the new `resource_distributions` table. It is designed to
be repeatable so that we can refresh distributions closer to the production cutover
date.

Usage examples:
    python db/migrations/migrate_document_distributions.py --dry-run
    python db/migrations/migrate_document_distributions.py --batch-size 2000
    python db/migrations/migrate_document_distributions.py --no-delete-existing

Environment variables follow the conventions used by other migration scripts:
    DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME      -> new database
    OLD_DB_NAME                                          -> old database name

The script logs a summary of migrated rows, skipped records, and any anomalies.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import bindparam

# Ensure project root is on the path for shared modules if needed
sys.path.append(str(Path(__file__).parent.parent))


logger = logging.getLogger(__name__)


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


def get_env(key: str, default: str) -> str:
    return os.getenv(key, default)


def get_old_engine() -> Engine:
    db_user = get_env("DB_USER", "postgres")
    db_password = get_env("DB_PASSWORD", "postgres")
    db_host = get_env("DB_HOST", "localhost")
    db_port = get_env("DB_PORT", "2345")
    old_db_name = get_env("OLD_DB_NAME", "geoportal_production_20251030")

    url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{old_db_name}"
    logger.info("Connecting to old database: %s", old_db_name)
    return create_engine(url)


def get_new_engine() -> Engine:
    db_user = get_env("DB_USER", "postgres")
    db_password = get_env("DB_PASSWORD", "postgres")
    db_host = get_env("DB_HOST", "localhost")
    db_port = get_env("DB_PORT", "2345")
    db_name = get_env("DB_NAME", "btaa_ogm_api")

    url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    logger.info("Connecting to new database: %s", db_name)
    return create_engine(url)


def load_distribution_type_mapping(old_engine: Engine, new_engine: Engine) -> Dict[int, int]:
    """Return a mapping from old reference_type_id to new distribution_type_id."""

    with old_engine.connect() as conn:
        old_rows = conn.execute(
            text(
                """
                SELECT id, name, reference_uri
                FROM reference_types
                ORDER BY id
                """
            )
        ).fetchall()

    with new_engine.connect() as conn:
        new_rows = conn.execute(
            text(
                """
                SELECT id, name, distribution_uri
                FROM distribution_types
                ORDER BY id
                """
            )
        ).fetchall()

    uri_to_new: Dict[str, Tuple[int, str]] = {
        row.distribution_uri: (row.id, row.name) for row in new_rows
    }

    mapping: Dict[int, int] = {}
    mismatches: List[str] = []

    for old_row in old_rows:
        new_match = uri_to_new.get(old_row.reference_uri)
        if not new_match:
            mismatches.append(
                f"Legacy reference_type '{old_row.name}' (id={old_row.id}) has URI"
                f" {old_row.reference_uri} with no match in distribution_types"
            )
            continue

        mapping[old_row.id] = new_match[0]

        if old_row.name != new_match[1]:
            logger.debug(
                "Name mismatch for reference/distribution type: %s vs %s",
                old_row.name,
                new_match[1],
            )

    if mismatches:
        error_msg = "\n".join(mismatches)
        raise RuntimeError(
            "Failed to map all reference types to distribution types:\n" + error_msg
        )

    logger.info("Mapped %s reference types to distribution types", len(mapping))
    return mapping


def ensure_unique_index(new_engine: Engine, dry_run: bool) -> None:
    if dry_run:
        logger.info("[DRY RUN] Skipping unique index creation check")
        return

    with new_engine.begin() as conn:
        logger.info(
            "Ensuring unique index exists on (resource_id, distribution_type_id, url)"
        )
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_resource_distributions_resource_type_url
                ON resource_distributions (resource_id, distribution_type_id, url)
                """
            )
        )


def delete_existing_records(new_engine: Engine, dry_run: bool, truncate: bool) -> None:
    if dry_run:
        logger.info("[DRY RUN] Skipping deletion of existing migration rows")
        return

    with new_engine.begin() as conn:
        if truncate:
            logger.info("Truncating resource_distributions (full refresh)")
            conn.execute(text("TRUNCATE TABLE resource_distributions RESTART IDENTITY"))
        else:
            logger.info(
                "Removing existing rows with import_distribution_id set (previous migrations)"
            )
            conn.execute(
                text(
                    "DELETE FROM resource_distributions"
                    " WHERE import_distribution_id IS NOT NULL"
                )
            )


def fetch_batch(old_engine: Engine, last_id: int, batch_size: int) -> List:
    with old_engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT id, friendlier_id, reference_type_id, url, label, position,
                       created_at, updated_at, import_distribution_id
                FROM document_distributions
                WHERE id > :last_id
                ORDER BY id
                LIMIT :limit
                """
            ),
            {"last_id": last_id, "limit": batch_size},
        )
        return result.fetchall()


def fetch_existing_resources(new_engine: Engine, resource_ids: Sequence[str]) -> Set[str]:
    if not resource_ids:
        return set()

    # Use SQLAlchemy expanding parameter for IN clause
    stmt = (
        text("SELECT id FROM resources WHERE id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        )
    )

    with new_engine.connect() as conn:
        result = conn.execute(stmt, {"ids": list(resource_ids)})
        return {row.id for row in result.fetchall()}


def coerce_timestamp(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def prepare_records(
    batch_rows: Sequence,
    resource_id_set: Set[str],
    type_mapping: Dict[int, int],
) -> Tuple[List[Dict], Dict[str, int]]:
    stats = {
        "processed": 0,
        "prepared": 0,
        "skipped_null_url": 0,
        "skipped_missing_resource": 0,
        "skipped_missing_type": 0,
    }

    prepared: List[Dict] = []

    for row in batch_rows:
        stats["processed"] += 1

        url = row.url.strip() if row.url else None
        if not url:
            stats["skipped_null_url"] += 1
            continue

        if resource_id_set and row.friendlier_id not in resource_id_set:
            stats["skipped_missing_resource"] += 1
            logger.debug(
                "Skipping distribution %s: resource %s not in new database",
                row.id,
                row.friendlier_id,
            )
            continue

        distribution_type_id = type_mapping.get(row.reference_type_id)
        if not distribution_type_id:
            stats["skipped_missing_type"] += 1
            logger.warning(
                "Skipping distribution %s: missing type mapping for reference_type_id=%s",
                row.id,
                row.reference_type_id,
            )
            continue

        label = row.label.strip() if row.label else None
        position = row.position if row.position is not None else 0

        prepared.append(
            {
                "resource_id": row.friendlier_id,
                "distribution_type_id": distribution_type_id,
                "url": url,
                "label": label,
                "position": position,
                "created_at": coerce_timestamp(row.created_at),
                "updated_at": coerce_timestamp(row.updated_at),
                "import_distribution_id": str(row.import_distribution_id or row.id),
            }
        )

    stats["prepared"] = len(prepared)
    return prepared, stats


def insert_records(new_engine: Engine, records: Sequence[Dict], dry_run: bool) -> int:
    if not records:
        return 0

    if dry_run:
        logger.debug("[DRY RUN] Would insert %s records", len(records))
        return len(records)

    insert_sql = text(
        """
        INSERT INTO resource_distributions (
            resource_id,
            distribution_type_id,
            url,
            label,
            position,
            created_at,
            updated_at,
            import_distribution_id
        ) VALUES (
            :resource_id,
            :distribution_type_id,
            :url,
            :label,
            :position,
            :created_at,
            :updated_at,
            :import_distribution_id
        )
        ON CONFLICT (resource_id, distribution_type_id, url)
        DO UPDATE SET
            label = EXCLUDED.label,
            position = EXCLUDED.position,
            updated_at = EXCLUDED.updated_at,
            import_distribution_id = EXCLUDED.import_distribution_id
        """
    )

    with new_engine.begin() as conn:
        result = conn.execute(insert_sql, list(records))

    return result.rowcount if hasattr(result, "rowcount") else len(records)


def gather_resource_ids(batch_rows: Sequence) -> List[str]:
    return list({row.friendlier_id for row in batch_rows if row.friendlier_id})


def migrate(
    batch_size: int,
    dry_run: bool,
    delete_existing: bool,
    truncate: bool,
    verify_resources: bool,
) -> None:
    old_engine = get_old_engine()
    new_engine = get_new_engine()

    type_mapping = load_distribution_type_mapping(old_engine, new_engine)

    ensure_unique_index(new_engine, dry_run=dry_run)

    if delete_existing or truncate:
        delete_existing_records(new_engine, dry_run=dry_run, truncate=truncate)

    stats_totals = {
        "processed": 0,
        "prepared": 0,
        "skipped_null_url": 0,
        "skipped_missing_resource": 0,
        "skipped_missing_type": 0,
        "inserted": 0,
    }

    last_id = 0
    batch_number = 0

    while True:
        batch = fetch_batch(old_engine, last_id=last_id, batch_size=batch_size)
        if not batch:
            break

        batch_number += 1
        logger.info("Processing batch %s (records %s-%s)", batch_number, last_id + 1, batch[-1].id)

        resource_ids = gather_resource_ids(batch)
        existing_resources: Set[str] = set(resource_ids)

        if verify_resources:
            existing_resources = fetch_existing_resources(new_engine, resource_ids)
            missing = set(resource_ids) - existing_resources
            if missing:
                logger.warning(
                    "%s resources from batch missing in new DB: %s",
                    len(missing),
                    sorted(list(missing))[:5],
                )

        prepared, batch_stats = prepare_records(batch, existing_resources, type_mapping)

        for key, value in batch_stats.items():
            stats_totals[key] += value

        inserted = insert_records(new_engine, prepared, dry_run)
        stats_totals["inserted"] += inserted

        logger.info(
            "Batch %s summary: prepared=%s inserted=%s skipped_null_url=%s skipped_missing_resource=%s",
            batch_number,
            batch_stats["prepared"],
            inserted,
            batch_stats["skipped_null_url"],
            batch_stats["skipped_missing_resource"],
        )

        last_id = batch[-1].id

    logger.info("\n%s", "=" * 80)
    logger.info("Document distributions migration complete")
    for key, value in stats_totals.items():
        logger.info("%s: %s", key, value)
    logger.info("%s\n", "=" * 80)


def parse_args(argv: Optional[Sequence[str]] = None):  # type: ignore[override]
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate legacy document distributions into the new schema"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of rows to process per batch (default: 1000)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run all logic without inserting or deleting data",
    )
    parser.add_argument(
        "--no-delete-existing",
        action="store_true",
        help="Skip deleting prior migrated rows (import_distribution_id IS NOT NULL)",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate resource_distributions before inserting (implies delete)",
    )
    parser.add_argument(
        "--skip-resource-check",
        action="store_true",
        help="Do not verify that resources already exist in the new database",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug-level logging",
    )

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    configure_logging(verbose=args.verbose)

    try:
        migrate(
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            delete_existing=(not args.no_delete_existing) or args.truncate,
            truncate=args.truncate,
            verify_resources=not args.skip_resource_check,
        )
    except SQLAlchemyError as exc:
        logger.error("Database error during migration: %s", exc)
        raise
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Migration failed: %s", exc)
        raise


if __name__ == "__main__":
    main()


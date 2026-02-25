#!/usr/bin/env python3
"""Migrate legacy document data dictionaries into resource data dictionaries."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Sequence

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

# Ensure project root is on the path for shared modules.
sys.path.append(str(Path(__file__).parent.parent))

from db.models import metadata, resource_data_dictionaries, resource_data_dictionary_entries

logger = logging.getLogger(__name__)


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


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
    db_name = get_env("DB_NAME", "btaa_geospatial_api")
    url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    logger.info("Connecting to new database: %s", db_name)
    return create_engine(url)


def ensure_tables(new_engine: Engine, dry_run: bool) -> None:
    if dry_run:
        logger.info("[DRY RUN] Skipping table creation")
        return
    _ = (resource_data_dictionaries, resource_data_dictionary_entries)
    metadata.create_all(new_engine)
    logger.info("Ensured resource data dictionary tables exist")


def delete_existing(new_engine: Engine, dry_run: bool, truncate: bool) -> None:
    if dry_run:
        logger.info("[DRY RUN] Skipping deletion of existing rows")
        return

    with new_engine.begin() as conn:
        if truncate:
            logger.info(
                "Truncating resource_data_dictionary_entries and resource_data_dictionaries"
            )
            conn.execute(
                text(
                    "TRUNCATE TABLE resource_data_dictionary_entries, "
                    "resource_data_dictionaries RESTART IDENTITY CASCADE"
                )
            )
            return

        logger.info("Deleting previously migrated rows (legacy_* ids present)")
        conn.execute(
            text(
                "DELETE FROM resource_data_dictionary_entries "
                "WHERE legacy_document_data_dictionary_entry_id IS NOT NULL"
            )
        )
        conn.execute(
            text(
                "DELETE FROM resource_data_dictionaries "
                "WHERE legacy_document_data_dictionary_id IS NOT NULL"
            )
        )


def migrate(batch_size: int, dry_run: bool, delete_first: bool, truncate: bool) -> None:
    old_engine = get_old_engine()
    new_engine = get_new_engine()

    ensure_tables(new_engine, dry_run=dry_run)
    if delete_first or truncate:
        delete_existing(new_engine, dry_run=dry_run, truncate=truncate)

    dict_total = 0
    entry_total = 0
    last_id = 0

    while True:
        with old_engine.connect() as old_conn:
            dictionaries = old_conn.execute(
                text(
                    """
                    SELECT id, friendlier_id, name, description, staff_notes, tags,
                           position, created_at, updated_at
                    FROM document_data_dictionaries
                    WHERE id > :last_id
                    ORDER BY id
                    LIMIT :limit
                    """
                ),
                {"last_id": last_id, "limit": batch_size},
            ).fetchall()

        if not dictionaries:
            break

        logger.info(
            "Processing dictionary batch: %s -> %s", dictionaries[0].id, dictionaries[-1].id
        )

        for dictionary in dictionaries:
            dict_total += 1
            if dry_run:
                continue

            with old_engine.connect() as old_conn:
                entries = old_conn.execute(
                    text(
                        """
                        SELECT id, field_name, field_type, values, definition, definition_source,
                               parent_field_name, position, created_at, updated_at
                        FROM document_data_dictionary_entries
                        WHERE document_data_dictionary_id = :legacy_dictionary_id
                        ORDER BY position, id
                        """
                    ),
                    {"legacy_dictionary_id": dictionary.id},
                ).fetchall()

            with new_engine.begin() as new_conn:
                new_dictionary_id = new_conn.execute(
                    text(
                        """
                        INSERT INTO resource_data_dictionaries (
                            resource_id,
                            legacy_document_data_dictionary_id,
                            name,
                            description,
                            staff_notes,
                            tags,
                            position,
                            created_at,
                            updated_at
                        )
                        VALUES (
                            :resource_id,
                            :legacy_document_data_dictionary_id,
                            :name,
                            :description,
                            :staff_notes,
                            :tags,
                            :position,
                            :created_at,
                            :updated_at
                        )
                        ON CONFLICT (legacy_document_data_dictionary_id)
                        DO UPDATE SET
                            resource_id = EXCLUDED.resource_id,
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            staff_notes = EXCLUDED.staff_notes,
                            tags = EXCLUDED.tags,
                            position = EXCLUDED.position,
                            updated_at = EXCLUDED.updated_at
                        RETURNING id
                        """
                    ),
                    {
                        "resource_id": dictionary.friendlier_id,
                        "legacy_document_data_dictionary_id": dictionary.id,
                        "name": dictionary.name,
                        "description": dictionary.description,
                        "staff_notes": dictionary.staff_notes,
                        "tags": dictionary.tags or "",
                        "position": dictionary.position if dictionary.position is not None else 0,
                        "created_at": dictionary.created_at,
                        "updated_at": dictionary.updated_at,
                    },
                ).scalar_one()

                for entry in entries:
                    entry_total += 1
                    new_conn.execute(
                        text(
                            """
                            INSERT INTO resource_data_dictionary_entries (
                                resource_data_dictionary_id,
                                legacy_document_data_dictionary_entry_id,
                                field_name,
                                field_type,
                                values,
                                definition,
                                definition_source,
                                parent_field_name,
                                position,
                                created_at,
                                updated_at
                            )
                            VALUES (
                                :resource_data_dictionary_id,
                                :legacy_document_data_dictionary_entry_id,
                                :field_name,
                                :field_type,
                                :values,
                                :definition,
                                :definition_source,
                                :parent_field_name,
                                :position,
                                :created_at,
                                :updated_at
                            )
                            ON CONFLICT (legacy_document_data_dictionary_entry_id)
                            DO UPDATE SET
                                resource_data_dictionary_id = EXCLUDED.resource_data_dictionary_id,
                                field_name = EXCLUDED.field_name,
                                field_type = EXCLUDED.field_type,
                                values = EXCLUDED.values,
                                definition = EXCLUDED.definition,
                                definition_source = EXCLUDED.definition_source,
                                parent_field_name = EXCLUDED.parent_field_name,
                                position = EXCLUDED.position,
                                updated_at = EXCLUDED.updated_at
                            """
                        ),
                        {
                            "resource_data_dictionary_id": new_dictionary_id,
                            "legacy_document_data_dictionary_entry_id": entry.id,
                            "field_name": entry.field_name,
                            "field_type": entry.field_type,
                            "values": entry.values,
                            "definition": entry.definition,
                            "definition_source": entry.definition_source,
                            "parent_field_name": entry.parent_field_name,
                            "position": entry.position if entry.position is not None else 0,
                            "created_at": entry.created_at,
                            "updated_at": entry.updated_at,
                        },
                    )

        last_id = dictionaries[-1].id

    logger.info("Resource data dictionary migration complete")
    logger.info("Dictionaries processed: %s", dict_total)
    logger.info("Entries processed: %s", entry_total)


def parse_args(argv: Optional[Sequence[str]] = None):  # type: ignore[override]
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate legacy document data dictionaries to resource_data_dictionaries"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Number of dictionaries to process per batch (default: 500)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without writing data",
    )
    parser.add_argument(
        "--no-delete-existing",
        action="store_true",
        help="Skip deleting previously migrated rows",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate resource data dictionary tables before insert",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    configure_logging(verbose=args.verbose)
    try:
        migrate(
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            delete_first=(not args.no_delete_existing) or args.truncate,
            truncate=args.truncate,
        )
    except SQLAlchemyError as exc:
        logger.error("Database error during migration: %s", exc)
        raise
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Migration failed: %s", exc)
        raise


if __name__ == "__main__":
    main()

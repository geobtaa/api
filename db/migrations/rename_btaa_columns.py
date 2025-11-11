#!/usr/bin/env python3
"""Rename BTAA-specific columns to restore original casing."""

import logging
import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

# Ensure project root on path for shared config if needed
sys.path.append(str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


COLUMN_RENAMES = [
    ("b1g_adms_supportedschema_sm", "b1g_adms_supportedSchema_sm"),
    ("b1g_dateaccessioned_sm", "b1g_dateAccessioned_sm"),
    ("b1g_dcat_endpointdescription_s", "b1g_dcat_endpointDescription_s"),
    ("b1g_dcat_endpointurl_s", "b1g_dcat_endpointURL_s"),
    ("b1g_dcat_inseries_sm", "b1g_dcat_inSeries_sm"),
    ("b1g_localcollectionlabel_sm", "b1g_localCollectionLabel_sm"),
    ("b1g_prov_softwareagent_sm", "b1g_prov_softwareAgent_sm"),
    ("b1g_prov_wasgeneratedby_sm", "b1g_prov_wasGeneratedBy_sm"),
]


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return url


def rename_btaa_columns():
    """Rename BTAA columns in the resources table back to camelCase."""
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api"
    )
    engine = create_engine(_normalize_database_url(database_url))

    with engine.connect() as conn:
        for old_name, new_name in COLUMN_RENAMES:
            logger.info("Processing column rename %s -> %s", old_name, new_name)

            existing_old = conn.execute(
                text(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'resources' AND column_name = :col
                    """
                ),
                {"col": old_name},
            ).fetchone()

            if not existing_old:
                logger.info("  Column %s does not exist; skipping", old_name)
                continue

            existing_new = conn.execute(
                text(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = 'resources' AND column_name = :col
                    """
                ),
                {"col": new_name},
            ).fetchone()

            if existing_new:
                logger.info(
                    "  Target column %s already exists; skipping rename of %s", new_name, old_name
                )
                continue

            logger.info("  Renaming column %s to %s", old_name, new_name)
            conn.execute(
                text(
                    f'ALTER TABLE resources RENAME COLUMN "{old_name}" TO "{new_name}"'
                )
            )
            conn.commit()

    logger.info("Completed BTAA column casing fixes.")


if __name__ == "__main__":
    rename_btaa_columns()

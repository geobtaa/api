#!/usr/bin/env python
"""
Backfill resource_distributions for resources that have dct_references_s
but no distribution rows (e.g. OGM-harvested resources added before distribution
sync was implemented).

Usage:
    python scripts/backfill_distributions.py [--batch-size N] [--dry-run]

Options:
    --batch-size N   Process N resources per batch (default: 500)
    --dry-run        Log what would be done without making changes
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def find_resources_missing_distributions(batch_size: int, offset: int):
    """
    Find resources that have dct_references_s but no resource_distributions rows.
    Returns list of (id, dct_references_s) dicts.
    """
    query = """
        SELECT r.id, r.dct_references_s
        FROM resources r
        LEFT JOIN resource_distributions rd ON r.id = rd.resource_id
        WHERE r.dct_references_s IS NOT NULL
          AND r.dct_references_s != ''
          AND r.dct_references_s != '{}'
          AND rd.id IS NULL
        ORDER BY r.id
        LIMIT :batch_size OFFSET :offset
    """
    rows = await database.fetch_all(query, {"batch_size": batch_size, "offset": offset})
    return [{"id": r["id"], "dct_references_s": r["dct_references_s"]} for r in rows]


async def backfill(batch_size: int = 500, dry_run: bool = False) -> tuple[int, int]:
    """
    Backfill resource_distributions for resources missing them.
    Returns (resources_processed, distributions_created).
    """
    from app.services.distribution_sync import sync_distributions_for_batch

    if not database.is_connected:
        await database.connect()

    total_processed = 0
    total_distributions = 0
    offset = 0

    while True:
        batch = await find_resources_missing_distributions(batch_size, offset)
        if not batch:
            break

        if dry_run:
            logger.info(
                "DRY RUN: Would sync %d resources (ids: %s...)",
                len(batch),
                ", ".join(b["id"] for b in batch[:5]) + ("..." if len(batch) > 5 else ""),
            )
            total_processed += len(batch)
            offset += batch_size
            continue

        synced, dist_count = await sync_distributions_for_batch(batch)
        total_processed += len(batch)
        total_distributions += dist_count
        offset += batch_size
        logger.info(
            "Processed batch: %d resources, %d distributions (running total: %d / %d)",
            len(batch),
            dist_count,
            total_processed,
            total_distributions,
        )

    return total_processed, total_distributions


def main():
    parser = argparse.ArgumentParser(description="Backfill resource_distributions")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Resources per batch (default: 500)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log without making changes",
    )
    args = parser.parse_args()

    try:
        processed, distributions = asyncio.run(
            backfill(batch_size=args.batch_size, dry_run=args.dry_run)
        )
        if args.dry_run:
            logger.info("DRY RUN complete. Would have processed %d resources.", processed)
        else:
            logger.info(
                "Backfill complete. Processed %d resources, created %d distributions.",
                processed,
                distributions,
            )
        return 0
    except Exception as e:
        logger.error("Backfill failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

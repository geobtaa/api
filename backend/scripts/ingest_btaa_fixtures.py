#!/usr/bin/env python3
"""
Ingest BTAA fixture JSON files into the database.

Reads all JSON files from data/fixtures/btaa_fixtures_data/ and imports them
using the OGMResourceImporter.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.ogm_harvest.importer import OGMResourceImporter
from db.database import database

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def load_json_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load a JSON file and return the parsed data."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return None


async def ingest_btaa_fixtures(fixtures_dir: Path, repo_name: str = "btaa_fixtures"):
    """
    Ingest all JSON fixture files from the specified directory.

    Args:
        fixtures_dir: Path to directory containing JSON fixture files
        repo_name: Repository name to use for tagging (default: "btaa_fixtures")
    """
    if not fixtures_dir.exists():
        logger.error(f"Fixtures directory not found: {fixtures_dir}")
        return

    # Find all JSON files
    json_files = list(fixtures_dir.glob("*.json"))
    if not json_files:
        logger.warning(f"No JSON files found in {fixtures_dir}")
        return

    logger.info(f"Found {len(json_files)} JSON files to ingest")

    # Initialize importer
    importer = OGMResourceImporter()

    # Load all records
    records: list[Tuple[Dict[str, Any], str]] = []

    for json_file in json_files:
        logger.info(f"Loading {json_file.name}...")
        record = await load_json_file(json_file)
        if record:
            # Use the directory name + filename as the source path for tracking
            source_path = f"{fixtures_dir.name}/{json_file.name}"
            records.append((record, source_path))
        else:
            logger.warning(f"Skipping {json_file.name} due to load error")

    if not records:
        logger.error("No valid records to import")
        return

    logger.info(f"Importing {len(records)} records into database...")

    # Import all records
    stats = await importer.upsert_records(
        repo_name=repo_name, records=records, source_commit_sha=None
    )

    logger.info("=" * 60)
    logger.info("Import completed!")
    logger.info(f"Processed: {stats['processed']}")
    logger.info(f"Imported: {stats['imported']}")
    logger.info(f"Skipped: {stats['skipped']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info("=" * 60)


async def main():
    """Main function."""
    try:
        # Ensure database connection
        if not database.is_connected:
            await database.connect()
            logger.info("Database connection established")

        # Fixtures dir: default btaa_fixtures_data, or first CLI arg (e.g. btaa_featured_resources).
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        fixtures_subdir = sys.argv[1] if len(sys.argv) > 1 else "btaa_fixtures_data"
        repo_name = (
            sys.argv[2]
            if len(sys.argv) > 2
            else fixtures_subdir.replace("_data", "").replace("-", "_")
        )
        fixtures_dir = project_root / "data" / "fixtures" / fixtures_subdir

        logger.info(f"Fixtures directory: {fixtures_dir} (repo_name={repo_name})")

        # Ingest fixtures
        await ingest_btaa_fixtures(fixtures_dir, repo_name=repo_name)

    except Exception as e:
        logger.error(f"Error in main: {e}", exc_info=True)
        raise
    finally:
        # Close database connection
        if database.is_connected:
            await database.disconnect()
            logger.info("Database connection closed")


if __name__ == "__main__":
    asyncio.run(main())

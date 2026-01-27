#!/usr/bin/env python3
"""
Ingest GBL fixture JSON files into the database.

Reads all JSON files from data/fixtures/gbl_fixtures_data/ and imports them
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
            # Handle array format - extract first element if it's an array
            if isinstance(data, list):
                return data[0] if data else None
            return data
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return None


async def ingest_gbl_fixtures(fixtures_dir: Path, repo_name: str = "gbl_fixtures"):
    """
    Ingest all JSON fixture files from the specified directory.

    Args:
        fixtures_dir: Path to directory containing JSON fixture files
        repo_name: Repository name to use for tagging (default: "gbl_fixtures")
    """
    if not fixtures_dir.exists():
        logger.error(f"Fixtures directory not found: {fixtures_dir}")
        return

    # Find all JSON files (exclude README.md if it's JSON)
    json_files = [f for f in fixtures_dir.glob("*.json") if f.name != "README.md"]
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
            # Use the filename as the source path for tracking
            source_path = f"gbl_fixtures_data/{json_file.name}"
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

        # Get fixtures directory
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        fixtures_dir = project_root / "data" / "fixtures" / "gbl_fixtures_data"

        # Ingest fixtures
        await ingest_gbl_fixtures(fixtures_dir, repo_name="gbl_fixtures")

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

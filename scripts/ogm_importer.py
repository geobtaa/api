#!/usr/bin/env python3
"""
OpenGeoMetadata Importer

Imports Aardvark schema records from harvested OpenGeoMetadata data into the database.
Only processes records that match the Aardvark schema version.
"""

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from tqdm import tqdm

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from db.models import resources
from scripts.ogm_harvester import OGMHarvester

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OGMImporter:
    """Imports OpenGeoMetadata Aardvark records into the database."""

    def __init__(
        self,
        ogm_path: Optional[str] = None,
        database_url: Optional[str] = None,
        batch_size: int = 500,
        dry_run: bool = False,
        timeout_seconds: int = 3600,  # 1 hour timeout
    ):
        """
        Initialize the importer.

        Args:
            ogm_path: Path to OpenGeoMetadata repositories
            database_url: Database connection URL
            batch_size: Number of records to process in each batch
            dry_run: If True, don't actually insert into database
        """
        self.ogm_path = ogm_path or os.path.join("data", "opengeometadata")
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api"
        )
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self.start_time = None
        self.should_stop = False

        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Convert async URL to sync URL
        if self.database_url.startswith("postgresql+asyncpg://"):
            self.database_url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")

        self.engine = create_engine(self.database_url)

        # Initialize harvester for Aardvark schema only
        self.harvester = OGMHarvester(ogm_path=self.ogm_path, schema_version="Aardvark")

    def _signal_handler(self, signum, frame):
        """Handle interrupt signals gracefully."""
        logger.info(f"Received signal {signum}, stopping import gracefully...")
        self.should_stop = True

    def _check_timeout(self) -> bool:
        """Check if we've exceeded the timeout."""
        if self.start_time and time.time() - self.start_time > self.timeout_seconds:
            logger.warning(f"Import timeout reached ({self.timeout_seconds} seconds)")
            return True
        return False

    def _count_total_records(self, limit: Optional[int] = None) -> int:
        """Count total records that will be processed."""
        count = 0
        try:
            for _ in self.harvester.docs_to_index():
                count += 1
                if limit and count >= limit:
                    break
        except Exception as e:
            logger.warning(f"Error counting records: {e}")
        return count

    def _clean_record_for_database(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean and prepare a record for database insertion.

        Args:
            record: The OGM record to clean

        Returns:
            Cleaned record ready for database insertion
        """
        cleaned = {}

        logger.debug(f"_clean_record_for_database: Processing {len(record)} fields")

        for key, value in record.items():
            logger.debug(f"  Processing field '{key}': {repr(value)} (type: {type(value)})")
            if value is None or value == "":
                cleaned[key] = None
                continue

            # Handle integer fields first (before general array handling)
            if key == "gbl_indexYear_im":
                logger.debug(f"    INTEGER FIELD '{key}': {repr(value)} (type: {type(value)})")
                if isinstance(value, list):
                    # Convert string numbers to integers
                    try:
                        cleaned[key] = [int(v) for v in value if str(v).isdigit()]
                        logger.debug(f"      -> List converted to integers: {repr(cleaned[key])}")
                    except (ValueError, TypeError) as e:
                        logger.debug(f"      -> Conversion failed: {e}, set to None")
                        cleaned[key] = None
                elif isinstance(value, (int, str)) and str(value).isdigit():
                    cleaned[key] = [int(value)]
                    logger.debug(f"      -> Single value converted to list: {repr(cleaned[key])}")
                else:
                    cleaned[key] = None
                    logger.debug("      -> Set to None")

            # Handle array fields (using proper OGM field names)
            elif key in [
                "dct_alternative_sm",
                "dct_description_sm",
                "dct_language_sm",
                "gbl_displayNote_sm",
                "dct_creator_sm",
                "dct_publisher_sm",
                "gbl_resourceClass_sm",
                "gbl_resourceType_sm",
                "dct_subject_sm",
                "dcat_theme_sm",
                "dcat_keyword_sm",
                "dct_temporal_sm",
                "gbl_dateRange_drsim",
                "dct_spatial_sm",
                "dct_relation_sm",
                "pcdm_memberOf_sm",
                "dct_isPartOf_sm",
                "dct_source_sm",
                "dct_isVersionOf_sm",
                "dct_replaces_sm",
                "dct_isReplacedBy_sm",
                "dct_rights_sm",
                "dct_rightsHolder_sm",
                "dct_license_sm",
                "dct_identifier_sm",
                "b1g_dct_mediator_sm",
                "b1g_geonames_sm",
                "b1g_language_sm",
                "b1g_creatorID_sm",
                "b1g_dct_conformsTo_sm",
                "b1g_dcat_spatialResolutionInMeters_sm",
                "b1g_geodcat_spatialResolutionAsText_sm",
                "b1g_dct_provenanceStatement_sm",
                "b1g_adminTags_sm",
            ]:
                logger.debug(f"    ARRAY FIELD '{key}': {repr(value)} (type: {type(value)})")
                if isinstance(value, list):
                    logger.debug(f"      -> List: keeping as-is: {repr(value)}")
                    cleaned[key] = value
                elif isinstance(value, str):
                    logger.debug("      -> String: checking for semicolon splitting")
                    # Don't split strings - they should already be arrays
                    # Only split if it looks like a semicolon-separated list
                    if ";" in value and not value.startswith("[") and not value.startswith("'"):
                        values = [v.strip() for v in value.split(";") if v.strip()]
                        cleaned[key] = values if values else None
                        logger.debug(f"      -> Split by semicolon: {repr(cleaned[key])}")
                    else:
                        # Keep as single string, not array
                        cleaned[key] = value.strip() if value.strip() else None
                        logger.debug(f"      -> Keep as string: {repr(cleaned[key])}")
                else:
                    cleaned[key] = [str(value)] if value else None
                    logger.debug(f"      -> Convert to list: {repr(cleaned[key])}")

            # Handle JSON fields
            elif key == "dct_references_s":
                if isinstance(value, str):
                    try:
                        # Try to parse as JSON
                        cleaned[key] = json.loads(value)
                    except json.JSONDecodeError:
                        # If not valid JSON, store as string
                        cleaned[key] = value
                elif isinstance(value, dict):
                    cleaned[key] = value
                else:
                    cleaned[key] = str(value) if value else None

            # Handle JSON fields for BTAA-specific data
            elif key == "b1g_access_s":
                if isinstance(value, str):
                    try:
                        cleaned[key] = json.loads(value)
                    except json.JSONDecodeError:
                        cleaned[key] = value
                elif isinstance(value, dict):
                    cleaned[key] = value
                else:
                    cleaned[key] = str(value) if value else None

            # Handle boolean fields
            elif key in ["gbl_suppressed_b", "gbl_georeferenced_b", "b1g_child_record_b"]:
                if isinstance(value, bool):
                    cleaned[key] = value
                elif isinstance(value, str):
                    if value.lower() in ["true", "1", "yes"]:
                        cleaned[key] = True
                    elif value.lower() in ["false", "0", "no"]:
                        cleaned[key] = False
                    else:
                        cleaned[key] = None
                else:
                    cleaned[key] = None

            # Handle all other fields as strings
            else:
                logger.debug(f"    STRING FIELD '{key}': {repr(value)} (type: {type(value)})")
                cleaned[key] = str(value).strip() if value else None
                logger.debug(f"      -> Converted to string: {repr(cleaned[key])}")

        logger.debug(
            f"_clean_record_for_database: Completed cleaning, returning {len(cleaned)} fields"
        )
        return cleaned

    def _prepare_record_for_database(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare record for database insertion.

        Args:
            record: The cleaned OGM record

        Returns:
            Record ready for database insertion
        """
        logger.debug(f"_prepare_record_for_database: Processing {len(record)} fields")
        prepared_record = {}

        for field, value in record.items():
            logger.debug(f"  Preparing field '{field}': {repr(value)} (type: {type(value)})")

            # Convert JSON fields to strings for database storage
            if field in ["dct_references_s", "b1g_access_s"] and isinstance(value, dict):
                prepared_record[field] = json.dumps(value)
                logger.debug(
                    f"    -> JSON field converted to string: {repr(prepared_record[field])}"
                )
            else:
                prepared_record[field] = value
                logger.debug(f"    -> Kept as-is: {repr(prepared_record[field])}")

        logger.debug(
            f"_prepare_record_for_database: Completed preparation, "
            f"returning {len(prepared_record)} fields"
        )
        return prepared_record

    def import_records(self, limit: Optional[int] = None) -> Dict[str, int]:
        """
        Import Aardvark records from harvested data into the database.

        Args:
            limit: Maximum number of records to process (for testing)

        Returns:
            Dictionary with import statistics
        """
        stats = {"processed": 0, "imported": 0, "skipped": 0, "errors": 0}

        batch = []
        self.start_time = time.time()

        logger.info(f"Starting import of Aardvark records from {self.ogm_path}")
        logger.info(f"Dry run mode: {self.dry_run}")

        # Initialize progress bar - use limit or estimate for large imports
        if limit and limit <= 10000:
            logger.info("Counting total records to process...")
            total_records = self._count_total_records(limit)
            logger.info(f"Found {total_records} records to process")
            if total_records == 0:
                logger.warning("No records found to import")
                return stats
        else:
            # For large imports, use dynamic progress bar
            logger.info("Using dynamic progress tracking for large import...")
            total_records = None

        # Initialize progress bar
        progress_bar = tqdm(total=total_records, desc="Importing records", unit="records")

        current_dir = None
        try:
            for record, path in self.harvester.docs_to_index():
                # Track directory changes for visibility
                path_obj = Path(path)
                record_dir = path_obj.parent.name
                if record_dir != current_dir:
                    current_dir = record_dir
                    logger.info(f"📁 Processing directory: {record_dir}")

                # Log progress every 1000 records within the same directory
                if stats["processed"] % 1000 == 0:
                    logger.info(
                        f"📊 Processed {stats['processed']} records (current dir: {record_dir})"
                    )

                # Check for timeout or stop signal
                if self.should_stop or self._check_timeout():
                    logger.info("Stopping import due to timeout or signal")
                    break

                if limit and stats["processed"] >= limit:
                    logger.info(f"Reached limit of {limit} records")
                    break

                try:
                    # Debug: Log the original record
                    logger.debug(f"Processing record from {path}")
                    logger.debug(
                        f"Original gbl_resourceClass_sm: {repr(record.get('gbl_resourceClass_sm'))}"
                    )

                    # Clean the record
                    cleaned_record = self._clean_record_for_database(record)
                    logger.debug(
                        f"Cleaned gbl_resourceClass_sm: "
                        f"{repr(cleaned_record.get('gbl_resourceClass_sm'))}"
                    )

                    # Prepare record for database
                    prepared_record = self._prepare_record_for_database(cleaned_record)
                    logger.debug(
                        f"Prepared gbl_resourceClass_sm: "
                        f"{repr(prepared_record.get('gbl_resourceClass_sm'))}"
                    )

                    # Ensure we have a valid ID
                    if not prepared_record.get("id"):
                        record_id = record.get("layer_slug_s") or record.get("dc_identifier_s")
                        if record_id:
                            prepared_record["id"] = record_id
                        else:
                            logger.warning(f"No valid ID found for record in {path}")
                            stats["skipped"] += 1
                            continue

                    # Normalize to ensure every model column has a value (or None)
                    normalized_record = {}
                    for col in resources.c:
                        normalized_record[col.name] = prepared_record.get(col.name)
                    batch.append(normalized_record)
                    stats["processed"] += 1

                    # Debug: Log the final record before adding to batch
                    logger.debug("Final record added to batch:")
                    logger.debug(
                        f"  gbl_resourceClass_sm: "
                        f"{repr(prepared_record.get('gbl_resourceClass_sm'))}"
                    )
                    logger.debug(
                        f"  gbl_resourceType_sm: {repr(prepared_record.get('gbl_resourceType_sm'))}"
                    )
                    logger.debug(
                        f"  gbl_indexYear_im: {repr(prepared_record.get('gbl_indexYear_im'))}"
                    )

                    # Process batch when it reaches batch_size
                    if len(batch) >= self.batch_size:
                        imported_count = self._process_batch(batch)
                        stats["imported"] += imported_count
                        stats["errors"] += len(batch) - imported_count
                        batch = []

                        # Update progress bar
                        progress_bar.update(self.batch_size)
                        progress_bar.set_postfix(
                            {"imported": stats["imported"], "errors": stats["errors"]}
                        )

                except Exception as e:
                    logger.error(f"Error processing record from {path}: {e}")
                    stats["errors"] += 1
                    continue

            # Process remaining batch
            if batch:
                imported_count = self._process_batch(batch)
                stats["imported"] += imported_count
                stats["errors"] += len(batch) - imported_count
                progress_bar.update(len(batch))

            # Close progress bar
            progress_bar.close()

            # Calculate elapsed time
            elapsed_time = time.time() - self.start_time
            logger.info(f"Import completed in {elapsed_time:.2f} seconds. Stats: {stats}")
            logger.info(f"Last directory processed: {current_dir}")
            return stats

        except Exception as e:
            logger.error(f"Error during import: {e}")
            progress_bar.close()
            raise
        finally:
            # Ensure progress bar is closed
            if "progress_bar" in locals():
                progress_bar.close()

    def _process_batch(self, batch: List[Dict[str, Any]]) -> int:
        """
        Process a batch of records.

        Args:
            batch: List of records to insert

        Returns:
            Number of successfully imported records
        """
        if self.dry_run:
            logger.info(f"DRY RUN: Would import {len(batch)} records")
            # Debug: Log the first record in the batch
            if batch:
                logger.debug("DRY RUN - First record in batch:")
                logger.debug(
                    f"  gbl_resourceClass_sm: {repr(batch[0].get('gbl_resourceClass_sm'))}"
                )
                logger.debug(f"  gbl_resourceType_sm: {repr(batch[0].get('gbl_resourceType_sm'))}")
                logger.debug(f"  gbl_indexYear_im: {repr(batch[0].get('gbl_indexYear_im'))}")
            return len(batch)

        try:
            # Debug: Log the first record before database insertion
            if batch:
                logger.debug("About to insert batch - First record:")
                logger.debug(
                    f"  gbl_resourceClass_sm: {repr(batch[0].get('gbl_resourceClass_sm'))}"
                )
                logger.debug(f"  gbl_resourceType_sm: {repr(batch[0].get('gbl_resourceType_sm'))}")
                logger.debug(f"  gbl_indexYear_im: {repr(batch[0].get('gbl_indexYear_im'))}")

            with self.engine.connect() as conn:
                # Debug: Log the exact data being sent to database
                logger.debug("Raw batch data for database insertion:")
                for i, record in enumerate(batch[:1]):  # Just log first record
                    logger.debug(f"  Record {i}:")
                    for key, value in record.items():
                        if key in [
                            "gbl_resourceClass_sm",
                            "gbl_resourceType_sm",
                            "gbl_indexYear_im",
                        ]:
                            logger.debug(f"    {key}: {repr(value)} (type: {type(value)})")

                # Perform UPSERT using SQLAlchemy
                # Build per-row VALUES to allow missing keys to default to NULL
                insert_stmt = insert(resources).values(batch)
                # Upsert on primary key id; update all columns from excluded
                update_map = {c.name: insert_stmt.excluded[c.name] for c in resources.c}
                stmt = insert_stmt.on_conflict_do_update(index_elements=["id"], set_=update_map)
                # Execute without passing parameters again (already embedded)
                conn.execute(stmt)
                conn.commit()
                logger.debug(f"Successfully imported {len(batch)} records")
                return len(batch)

        except Exception as e:
            logger.error(f"Error importing batch of {len(batch)} records: {e}")
            # Log detailed error information
            logger.error(f"Error type: {type(e).__name__}")
            if hasattr(e, "orig") and e.orig:
                logger.error(f"Database error: {e.orig}")
            return 0


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(description="OpenGeoMetadata Importer")
    parser.add_argument(
        "--ogm-path",
        default=os.path.join("data", "opengeometadata"),
        help="Path to OpenGeoMetadata repositories",
    )
    parser.add_argument("--database-url", help="Database connection URL")
    parser.add_argument(
        "--batch-size", type=int, default=500, help="Batch size for database inserts"
    )
    parser.add_argument(
        "--timeout", type=int, default=3600, help="Timeout in seconds (default: 3600 = 1 hour)"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of records to process (for testing)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Don't actually insert into database"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create importer
    importer = OGMImporter(
        ogm_path=args.ogm_path,
        database_url=args.database_url,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout,
    )

    # Run import
    stats = importer.import_records(limit=args.limit)

    print("\nImport Summary:")
    print(f"  Processed: {stats['processed']}")
    print(f"  Imported: {stats['imported']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"  Errors: {stats['errors']}")


if __name__ == "__main__":
    main()

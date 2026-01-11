#!/usr/bin/env python3
"""
Populate Resource Distributions

This script extracts distribution data from the dct_references_s JSON field
in the resources table and creates corresponding records in resource_distributions.

Usage:
    python scripts/populate_distributions.py

Requirements:
    - PostgreSQL database with resources table
    - resource_distributions table created
    - distribution_types table populated
    - DATABASE_URL environment variable set
"""

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def populate_resource_distributions():
    """
    Populate the resource_distributions table from existing dct_references_s data.

    This script extracts distribution data from the dct_references_s JSON field
    in the resources table and creates corresponding records in resource_distributions.
    """
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api"
        )
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

        # Create engine
        engine = create_engine(sync_database_url)

        logger.info("Populating resource_distributions from dct_references_s...")

        with engine.connect() as conn:
            # First, clear existing distributions
            logger.info("Clearing existing distributions...")
            conn.execute(text("TRUNCATE TABLE resource_distributions"))
            conn.commit()
            logger.info("Existing distributions cleared")

            # Check if we have any resources with dct_references_s
            result = conn.execute(
                text("""
                SELECT COUNT(*) as count 
                FROM resources 
                WHERE dct_references_s IS NOT NULL 
                AND dct_references_s != ''
                AND dct_references_s != '{}'
            """)
            )
            total_resources = result.fetchone()[0]
            logger.info(f"Found {total_resources} resources with dct_references_s data")

            if total_resources == 0:
                logger.info("No resources with dct_references_s data found. Skipping population.")
                return

            # Get all resources with dct_references_s data
            result = conn.execute(
                text("""
                SELECT id, dct_references_s 
                FROM resources 
                WHERE dct_references_s IS NOT NULL 
                AND dct_references_s != ''
                AND dct_references_s != '{}'
            """)
            )

            resources = result.fetchall()
            logger.info(f"Processing {len(resources)} resources...")

            # Create a mapping of distribution URIs to type IDs
            uri_to_type_id = {}
            type_result = conn.execute(
                text("""
                SELECT id, distribution_uri FROM distribution_types
            """)
            )
            for type_id, uri in type_result.fetchall():
                uri_to_type_id[uri] = type_id

            logger.info(f"Loaded {len(uri_to_type_id)} distribution type mappings")

            # Process each resource
            processed_count = 0
            error_count = 0

            for resource_id, dct_references_s in resources:
                try:
                    # Parse the JSON string
                    if isinstance(dct_references_s, str):
                        try:
                            references = json.loads(dct_references_s)
                        except json.JSONDecodeError:
                            logger.warning(
                                f"Failed to parse JSON for resource {resource_id}: "
                                f"{dct_references_s[:100]}..."
                            )
                            error_count += 1
                            continue
                    else:
                        # Already a dict/object
                        references = dct_references_s

                    if not isinstance(references, dict):
                        logger.warning(
                            f"References not a dict for resource {resource_id}: {type(references)}"
                        )
                        error_count += 1
                        continue

                    # Process each reference
                    position = 0
                    for uri, url_data in references.items():
                        if uri in uri_to_type_id:
                            # Handle different URL data structures
                            if isinstance(url_data, list):
                                # Multiple distributions for this URI
                                for item in url_data:
                                    if isinstance(item, dict):
                                        # Extract URL and label from object
                                        actual_url = item.get("url", "")
                                        label = item.get("label", "")
                                    else:
                                        # Fallback if item is not a dict
                                        actual_url = str(item)
                                        label = ""

                                    if actual_url:  # Only insert if we have a valid URL
                                        conn.execute(
                                            text("""
                                            INSERT INTO resource_distributions 
                                            (resource_id, distribution_type_id, url, 
                                             label, position)
                                            VALUES (:resource_id, :distribution_type_id, 
                                                    :url, :label, :position)
                                            ON CONFLICT DO NOTHING
                                        """),
                                            {
                                                "resource_id": resource_id,
                                                "distribution_type_id": uri_to_type_id[uri],
                                                "url": actual_url,
                                                "label": label,
                                                "position": position,
                                            },
                                        )
                                        position += 1
                            else:
                                # Single distribution (string URL)
                                conn.execute(
                                    text("""
                                    INSERT INTO resource_distributions 
                                    (resource_id, distribution_type_id, url, position)
                                    VALUES (:resource_id, :distribution_type_id, :url, :position)
                                    ON CONFLICT DO NOTHING
                                """),
                                    {
                                        "resource_id": resource_id,
                                        "distribution_type_id": uri_to_type_id[uri],
                                        "url": str(url_data),
                                        "position": position,
                                    },
                                )
                                position += 1
                        else:
                            logger.debug(
                                f"Unknown distribution URI for resource {resource_id}: {uri}"
                            )

                    processed_count += 1

                    if processed_count % 1000 == 0:
                        logger.info(f"Processed {processed_count} resources...")
                        conn.commit()

                except Exception as e:
                    logger.error(f"Error processing resource {resource_id}: {e}")
                    error_count += 1
                    continue

            # Final commit
            conn.commit()

            logger.info("✓ Population complete!")
            logger.info(f"  - Processed: {processed_count} resources")
            logger.info(f"  - Errors: {error_count} resources")

            # Get final count of distributions
            result = conn.execute(text("SELECT COUNT(*) FROM resource_distributions"))
            total_distributions = result.fetchone()[0]
            logger.info(f"  - Total distributions created: {total_distributions}")

            # Show distribution by type
            logger.info("Distribution by type:")
            result = conn.execute(
                text("""
                SELECT dt.distribution_type, COUNT(rd.id) as count
                FROM distribution_types dt
                LEFT JOIN resource_distributions rd ON dt.id = rd.distribution_type_id
                GROUP BY dt.id, dt.distribution_type
                ORDER BY count DESC
            """)
            )

            for type_name, count in result.fetchall():
                logger.info(f"  - {type_name}: {count} distributions")

    except Exception as e:
        logger.error(f"Error populating resource_distributions: {e}")
        raise


if __name__ == "__main__":
    populate_resource_distributions()

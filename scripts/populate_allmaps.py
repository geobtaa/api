#!/usr/bin/env python3
"""
Populate Allmaps Data

This script submits all resources with IIIF manifests to the Celery queue for
background processing of Allmaps data (manifest fetching, annotation checking).

For each resource with a IIIF manifest:
1. Fetches and validates the IIIF manifest (v2 or v3)
2. Generates an Allmaps ID from the manifest
3. Checks for existing Allmaps annotations
4. Stores the data in the resource_allmaps table

Usage:
    python scripts/populate_allmaps.py [options]

Options:
    --batch-size: Number of resources per batch (default: 100)
    --dry-run: Show what would be submitted without actually submitting

Requirements:
    - PostgreSQL database with resources table
    - resource_allmaps table created
    - Celery workers running
    - DATABASE_URL environment variable set
"""

import argparse
import logging
import os
import sys

from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Celery to connect to Docker Redis
celery_app = Celery(
    "tasks",
    broker=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/0",
    backend=f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', 6379)}/0",
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def main():
    """Main function to handle command line arguments and submit jobs."""
    parser = argparse.ArgumentParser(
        description="Populate Allmaps data for resources with IIIF manifests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Submit jobs with default settings
  python scripts/populate_allmaps.py
  
  # Submit with custom batch size
  python scripts/populate_allmaps.py --batch-size 50
  
  # Dry run to see what would be submitted
  python scripts/populate_allmaps.py --dry-run
        """,
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of resources per batch (default: 100)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be submitted without actually submitting",
    )

    args = parser.parse_args()

    try:
        if args.dry_run:
            logger.info("🔍 DRY RUN MODE - No jobs will be submitted")
            logger.info(f"Would submit jobs with batch_size={args.batch_size}")
            return 0

        logger.info("Submitting Allmaps processing jobs to Celery...")
        logger.info(f"Batch size: {args.batch_size}")

        # Submit the job - send it with arguments
        result = celery_app.send_task("index_all_allmaps", args=[args.batch_size])

        logger.info("✅ Successfully submitted Allmaps processing job!")
        logger.info(f"Task ID: {result.id}")
        logger.info("You can monitor progress using Flower or Celery monitoring tools")
        logger.info("")
        logger.info("Note: The script now supports both IIIF v2 and v3 manifests")

        return 0

    except KeyboardInterrupt:
        logger.info("Job submission interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Error submitting jobs: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

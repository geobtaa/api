#!/usr/bin/env python
"""
Script to run database migrations.

This script provides a command-line interface for running database migrations.
It supports multiple migration types and provides logging of the migration process.

Available Migrations:
    add_fast_gazetteer: Adds FAST gazetteer data to the database
    optimize_spatial_queries: Optimizes spatial queries with indexes and materialized views
    rollback_spatial_optimizations: Rolls back spatial query optimizations (WARNING: makes queries slower)

Usage:
    python scripts/run_migration.py [migration_name]
"""

import argparse
import logging
import os
import sys

# Add the parent directory to the path so we can import the app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import migration modules
from db.migrations.add_fast_gazetteer import add_fast_gazetteer
from db.migrations.optimize_spatial_queries import optimize_spatial_queries
from db.migrations.rollback_spatial_optimizations import rollback_spatial_optimizations

# Configure logging with standard format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def main():
    """
    Run the specified database migration.

    This function:
    1. Parses command line arguments
    2. Executes the specified migration
    3. Logs the progress and results

    Returns:
        int: 0 on success, 1 on error
    """
    # Set up command line argument parser
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument(
        "migration",
        choices=["add_fast_gazetteer", "optimize_spatial_queries", "rollback_spatial_optimizations"],
        help="The migration to run",
    )

    # Parse command line arguments
    args = parser.parse_args()

    try:
        # Execute the specified migration
        if args.migration == "add_fast_gazetteer":
            logger.info("Running add_fast_gazetteer migration")
            add_fast_gazetteer()
            logger.info("Migration completed successfully")
        elif args.migration == "optimize_spatial_queries":
            logger.info("Running optimize_spatial_queries migration")
            optimize_spatial_queries()
            logger.info("Migration completed successfully")
        elif args.migration == "rollback_spatial_optimizations":
            logger.warning("Running rollback_spatial_optimizations migration")
            rollback_spatial_optimizations()
            logger.warning("Rollback completed successfully")
        else:
            logger.error(f"Unknown migration: {args.migration}")
            return 1

        return 0

    except Exception as e:
        logger.error(f"Error running migration: {e}")
        return 1


if __name__ == "__main__":
    # Run the main function and exit with appropriate status code
    sys.exit(main())

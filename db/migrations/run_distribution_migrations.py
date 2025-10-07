#!/usr/bin/env python3
"""
Run all distribution-related migrations in the correct order.

This script:
1. Creates the distribution_types table with data
2. Creates the resource_distributions table
3. Populates resource_distributions from existing dct_references_s data
"""

import logging
import sys
import os
from pathlib import Path

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_distribution_migrations():
    """
    Run all distribution-related migrations in sequence.
    """
    try:
        logger.info("🚀 Starting distribution migrations...")
        
        # Import and run the table creation migration
        logger.info("Step 1: Creating distribution tables...")
        from create_distribution_tables import create_distribution_tables
        create_distribution_tables()
        
        # Import and run the data population migration
        logger.info("Step 2: Populating resource distributions...")
        from populate_resource_distributions import populate_resource_distributions
        populate_resource_distributions()
        
        logger.info("🎉 All distribution migrations completed successfully!")
        logger.info("")
        logger.info("Summary:")
        logger.info("  ✓ distribution_types table created with 28 reference types")
        logger.info("  ✓ resource_distributions table created with proper indexes")
        logger.info("  ✓ resource_distributions populated from existing dct_references_s data")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Verify the data: SELECT COUNT(*) FROM resource_distributions;")
        logger.info("  2. Update your application code to use the new tables")
        logger.info("  3. Consider deprecating the dct_references_s field in favor of the new structure")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    run_distribution_migrations()

#!/usr/bin/env python3
"""
Test script to verify the distribution migrations work correctly.
"""

import logging
import sys
import os
from pathlib import Path

from sqlalchemy import create_engine, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_distribution_migrations():
    """
    Test that the distribution migrations worked correctly.
    """
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)

        logger.info("🧪 Testing distribution migrations...")

        with engine.connect() as conn:
            # Test 1: Check that distribution_types table exists and has data
            logger.info("Test 1: Checking distribution_types table...")
            result = conn.execute(text("SELECT COUNT(*) FROM distribution_types"))
            type_count = result.fetchone()[0]
            logger.info(f"  ✓ distribution_types has {type_count} records")
            
            if type_count == 0:
                logger.error("  ❌ distribution_types table is empty!")
                return False

            # Test 2: Check that resource_distributions table exists
            logger.info("Test 2: Checking resource_distributions table...")
            result = conn.execute(text("SELECT COUNT(*) FROM resource_distributions"))
            dist_count = result.fetchone()[0]
            logger.info(f"  ✓ resource_distributions has {dist_count} records")

            # Test 3: Check foreign key relationship
            logger.info("Test 3: Checking foreign key relationships...")
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM resource_distributions rd
                JOIN distribution_types dt ON rd.distribution_type_id = dt.id
            """))
            valid_relationships = result.fetchone()[0]
            logger.info(f"  ✓ {valid_relationships} valid foreign key relationships")

            # Test 4: Check for some specific distribution types
            logger.info("Test 4: Checking for specific distribution types...")
            result = conn.execute(text("""
                SELECT name, distribution_type 
                FROM distribution_types 
                WHERE name IN ('download', 'image', 'iiif_image')
                ORDER BY name
            """))
            
            expected_types = ['download', 'image', 'iiif_image']
            found_types = []
            for name, dist_type in result.fetchall():
                found_types.append(name)
                logger.info(f"  ✓ Found {name}: {dist_type}")
            
            for expected in expected_types:
                if expected not in found_types:
                    logger.warning(f"  ⚠️  Expected type '{expected}' not found")

            # Test 5: Check distribution statistics
            logger.info("Test 5: Distribution statistics...")
            result = conn.execute(text("""
                SELECT dt.distribution_type, COUNT(rd.id) as count
                FROM distribution_types dt
                LEFT JOIN resource_distributions rd ON dt.id = rd.distribution_type_id
                GROUP BY dt.id, dt.distribution_type
                ORDER BY count DESC
                LIMIT 10
            """))
            
            logger.info("  Top 10 distribution types by usage:")
            for type_name, count in result.fetchall():
                logger.info(f"    - {type_name}: {count}")

            # Test 6: Check for any orphaned records
            logger.info("Test 6: Checking for orphaned records...")
            result = conn.execute(text("""
                SELECT COUNT(*) 
                FROM resource_distributions rd
                LEFT JOIN distribution_types dt ON rd.distribution_type_id = dt.id
                WHERE dt.id IS NULL
            """))
            orphaned_count = result.fetchone()[0]
            
            if orphaned_count > 0:
                logger.error(f"  ❌ Found {orphaned_count} orphaned records!")
                return False
            else:
                logger.info("  ✓ No orphaned records found")

            logger.info("🎉 All tests passed!")
            return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    success = test_distribution_migrations()
    sys.exit(0 if success else 1)

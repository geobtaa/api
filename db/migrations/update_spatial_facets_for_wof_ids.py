import logging
import sys
import os
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def update_spatial_facets_for_wof_ids():
    """
    Update the resource_spatial_facets table to store WOF identifiers.
    
    This migration:
    1. Changes geo_country from VARCHAR to JSONB to store WOF objects
    2. Updates geo_region and geo_county to store WOF objects instead of simple strings
    3. Adds new indexes for WOF ID queries
    4. Clears existing data (since format has changed significantly)
    """
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        logger.info("Updating resource_spatial_facets table for WOF identifiers...")

        with engine.connect() as conn:
            # Check if table exists
            if not inspector.has_table("resource_spatial_facets"):
                logger.warning("resource_spatial_facets table does not exist. Please run create_resource_spatial_facets_table.py first.")
                return

            # Clear existing data since the format has changed significantly
            logger.info("Clearing existing spatial facet data (format has changed)...")
            conn.execute(text("TRUNCATE TABLE resource_spatial_facets;"))
            conn.commit()
            logger.info("✓ Existing data cleared")

            # Drop existing indexes
            logger.info("Dropping existing indexes...")
            try:
                conn.execute(text("DROP INDEX IF EXISTS idx_resource_spatial_facets_geo_country;"))
                conn.execute(text("DROP INDEX IF EXISTS idx_resource_spatial_facets_geo_region_gin;"))
                conn.execute(text("DROP INDEX IF EXISTS idx_resource_spatial_facets_geo_county_gin;"))
                conn.commit()
            except Exception as e:
                logger.warning(f"Some indexes may not exist: {e}")
            logger.info("✓ Existing indexes dropped")

            # Update table structure
            logger.info("Updating table structure...")
            
            # Change geo_country from VARCHAR to JSONB
            conn.execute(text("""
                ALTER TABLE resource_spatial_facets 
                ALTER COLUMN geo_country TYPE JSONB 
                USING CASE 
                    WHEN geo_country IS NULL THEN NULL
                    ELSE to_jsonb(geo_country::text)
                END;
            """))
            
            # geo_region and geo_county are already JSONB, but we'll ensure they're properly configured
            conn.commit()
            logger.info("✓ Table structure updated")

            # Create new indexes optimized for WOF identifier queries
            logger.info("Creating new indexes for WOF identifiers...")
            
            # GIN index on geo_country JSONB for WOF object queries
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_spatial_facets_geo_country_gin 
                ON resource_spatial_facets USING GIN (geo_country);
            """))
            
            # GIN index on geo_region JSONB for WOF object queries
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_spatial_facets_geo_region_gin 
                ON resource_spatial_facets USING GIN (geo_region);
            """))
            
            # GIN index on geo_county JSONB for WOF object queries
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_spatial_facets_geo_county_gin 
                ON resource_spatial_facets USING GIN (geo_county);
            """))
            
            # Index on updated_at for tracking changes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_spatial_facets_updated_at 
                ON resource_spatial_facets (updated_at);
            """))
            
            conn.commit()
            logger.info("✓ New indexes created")

            # Update table statistics
            logger.info("Updating table statistics...")
            conn.execute(text("ANALYZE resource_spatial_facets;"))
            conn.commit()
            logger.info("✓ Table statistics updated")

        logger.info("🎉 resource_spatial_facets table updated successfully for WOF identifiers!")
        logger.info("New table structure:")
        logger.info("  - resource_id: Primary key, foreign key to resources")
        logger.info("  - geo_country: JSONB object with {name, wok_id, parent_id}")
        logger.info("  - geo_region: JSONB array of objects with {name, wok_id, parent_id}")
        logger.info("  - geo_county: JSONB array of objects with {name, wok_id, parent_id, state_abbrev}")
        logger.info("  - created_at/updated_at: Timestamps with auto-update trigger")
        logger.info("")
        logger.info("⚠️  IMPORTANT: All existing spatial facet data has been cleared.")
        logger.info("   You will need to re-run the spatial facet indexing to populate with WOF identifiers.")

    except Exception as e:
        logger.error(f"Error updating resource_spatial_facets table: {e}")
        raise


if __name__ == "__main__":
    update_spatial_facets_for_wof_ids()

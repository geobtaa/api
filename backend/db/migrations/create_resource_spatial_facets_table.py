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


def create_resource_spatial_facets_table():
    """
    Create the resource_spatial_facets table for storing pre-computed spatial facets.
    
    This table stores the results of spatial facet calculations for each resource,
    allowing for fast faceting in search results without on-the-fly computation.
    """
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        logger.info("Creating resource_spatial_facets table...")

        with engine.connect() as conn:
            # Create the table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS resource_spatial_facets (
                    resource_id VARCHAR(255) PRIMARY KEY,
                    geo_global BOOLEAN DEFAULT FALSE,
                    geo_country JSONB,
                    geo_region JSONB,
                    geo_county JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
                );
            """))
            conn.commit()
        logger.info("✓ Table created")

        # Create indexes for fast querying
        logger.info("Creating indexes...")
        with engine.connect() as conn:
            # Index on geo_global for filtering global datasets
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_spatial_facets_geo_global 
                ON resource_spatial_facets (geo_global);
            """))
            
            # GIN index on geo_country JSONB for array operations
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_spatial_facets_geo_country_gin 
                ON resource_spatial_facets USING GIN (geo_country);
            """))
            
            # GIN index on geo_region JSONB for array operations
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_spatial_facets_geo_region_gin 
                ON resource_spatial_facets USING GIN (geo_region);
            """))
            
            # GIN index on geo_county JSONB for array operations
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
        logger.info("✓ Indexes created")

        # Add trigger to update updated_at timestamp
        logger.info("Creating update trigger...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION update_resource_spatial_facets_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """))
            
            conn.execute(text("""
                DROP TRIGGER IF EXISTS trigger_update_resource_spatial_facets_updated_at 
                ON resource_spatial_facets;
            """))
            
            conn.execute(text("""
                CREATE TRIGGER trigger_update_resource_spatial_facets_updated_at
                    BEFORE UPDATE ON resource_spatial_facets
                    FOR EACH ROW
                    EXECUTE FUNCTION update_resource_spatial_facets_updated_at();
            """))
            
            conn.commit()
        logger.info("✓ Update trigger created")

        # Analyze the table
        logger.info("Updating table statistics...")
        with engine.connect() as conn:
            conn.execute(text("ANALYZE resource_spatial_facets;"))
            conn.commit()
        logger.info("✓ Table statistics updated")

        logger.info("🎉 resource_spatial_facets table created successfully!")
        logger.info("Table structure:")
        logger.info("  - resource_id: Primary key, foreign key to resources")
        logger.info("  - geo_global: Boolean flag for global datasets (entire world)")
        logger.info("  - geo_country: JSONB array of country names")
        logger.info("  - geo_region: JSONB array of region/state names")
        logger.info("  - geo_county: JSONB array of county names with state prefixes")
        logger.info("  - created_at/updated_at: Timestamps with auto-update trigger")

    except Exception as e:
        logger.error(f"Error creating resource_spatial_facets table: {e}")
        raise


if __name__ == "__main__":
    create_resource_spatial_facets_table()

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


def rollback_spatial_optimizations():
    """
    Rollback spatial query optimizations.
    
    This migration removes:
    1. The materialized view for county-state relationships
    2. All spatial and composite indexes created for optimization
    3. The geometry column from gazetteer_wof_geojson
    
    WARNING: This will make spatial queries significantly slower!
    """
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        logger.warning("Starting rollback of spatial query optimizations...")
        logger.warning("WARNING: This will make spatial queries significantly slower!")

        # 1. Drop materialized view
        logger.info("1. Dropping materialized view...")
        with engine.connect() as conn:
            conn.execute(text("DROP MATERIALIZED VIEW IF EXISTS county_state_relationships;"))
            conn.commit()
        logger.info("✓ Materialized view dropped")

        # 2. Drop indexes on gazetteer_wof_geojson
        logger.info("2. Dropping spatial and composite indexes...")
        with engine.connect() as conn:
            # Drop spatial index
            conn.execute(text("DROP INDEX IF EXISTS idx_gazetteer_wof_geojson_geometry_gist;"))
            
            # Drop composite index
            conn.execute(text("DROP INDEX IF EXISTS idx_gazetteer_wof_geojson_source_alt_label_geometry;"))
            
            conn.commit()
        logger.info("✓ Indexes on gazetteer_wof_geojson dropped")

        # 3. Drop indexes on gazetteer_wof_spr
        logger.info("3. Dropping composite indexes on gazetteer_wof_spr...")
        with engine.connect() as conn:
            # Drop parent_id index
            conn.execute(text("DROP INDEX IF EXISTS idx_gazetteer_wof_spr_parent_id;"))
            
            # Drop county index
            conn.execute(text("DROP INDEX IF EXISTS idx_gazetteer_wof_spr_county_us;"))
            
            # Drop region index
            conn.execute(text("DROP INDEX IF EXISTS idx_gazetteer_wof_spr_region_us;"))
            
            conn.commit()
        logger.info("✓ Indexes on gazetteer_wof_spr dropped")

        # 4. Drop geometry column
        logger.info("4. Dropping geometry column from gazetteer_wof_geojson...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE gazetteer_wof_geojson DROP COLUMN IF EXISTS geometry;"))
            conn.commit()
        logger.info("✓ Geometry column dropped")

        # 5. Update table statistics
        logger.info("5. Updating table statistics...")
        with engine.connect() as conn:
            conn.execute(text("ANALYZE gazetteer_wof_geojson;"))
            conn.execute(text("ANALYZE gazetteer_wof_spr;"))
            conn.commit()
        logger.info("✓ Table statistics updated")

        logger.warning("⚠️  Spatial query optimizations have been rolled back!")
        logger.warning("⚠️  Spatial queries will now be significantly slower (4x slower).")

    except Exception as e:
        logger.error(f"Error rolling back spatial optimizations: {e}")
        raise


if __name__ == "__main__":
    rollback_spatial_optimizations()

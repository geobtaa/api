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


def create_resource_distributions_table():
    """
    Create the resource_distributions table for storing resource distribution data.
    
    This table stores distribution information derived from the dct_references_s field
    in the resources table, with relationships to distribution_types.
    """
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        logger.info("Creating resource_distributions table...")

        with engine.connect() as conn:
            # Create the table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS resource_distributions (
                    id SERIAL PRIMARY KEY,
                    friendlier_id VARCHAR(255) NOT NULL,
                    distribution_type_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    label VARCHAR(255),
                    position INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    import_distribution_id VARCHAR(255),
                    FOREIGN KEY (distribution_type_id) REFERENCES distribution_types(id) ON DELETE RESTRICT
                );
            """))
            conn.commit()
        logger.info("✓ Table created")

        # Create indexes for fast querying
        logger.info("Creating indexes...")
        with engine.connect() as conn:
            # Index on friendlier_id for lookups by resource
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_distributions_friendlier_id 
                ON resource_distributions (friendlier_id);
            """))
            
            # Index on distribution_type_id for filtering by type
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_distributions_distribution_type_id 
                ON resource_distributions (distribution_type_id);
            """))
            
            # Index on url for lookups
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_distributions_url 
                ON resource_distributions (url);
            """))
            
            # Index on position for ordering
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_distributions_position 
                ON resource_distributions (position);
            """))
            
            # Index on import_distribution_id for tracking imports
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_distributions_import_distribution_id 
                ON resource_distributions (import_distribution_id);
            """))
            
            # Composite index for common queries
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_resource_distributions_friendlier_id_type 
                ON resource_distributions (friendlier_id, distribution_type_id);
            """))
            
            conn.commit()
        logger.info("✓ Indexes created")

        # Add trigger to update updated_at timestamp
        logger.info("Creating update trigger...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION update_resource_distributions_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """))
            
            conn.execute(text("""
                DROP TRIGGER IF EXISTS trigger_update_resource_distributions_updated_at 
                ON resource_distributions;
            """))
            
            conn.execute(text("""
                CREATE TRIGGER trigger_update_resource_distributions_updated_at
                    BEFORE UPDATE ON resource_distributions
                    FOR EACH ROW
                    EXECUTE FUNCTION update_resource_distributions_updated_at();
            """))
            
            conn.commit()
        logger.info("✓ Update trigger created")

        # Analyze the table
        logger.info("Updating table statistics...")
        with engine.connect() as conn:
            conn.execute(text("ANALYZE resource_distributions;"))
            conn.commit()
        logger.info("✓ Table statistics updated")

        logger.info("🎉 resource_distributions table created successfully!")
        logger.info("Table structure:")
        logger.info("  - id: Primary key")
        logger.info("  - friendlier_id: Reference to the resource (matches resources.id)")
        logger.info("  - distribution_type_id: Foreign key to distribution_types")
        logger.info("  - url: The distribution URL")
        logger.info("  - label: Optional label for the distribution")
        logger.info("  - position: Ordering position")
        logger.info("  - created_at/updated_at: Timestamps with auto-update trigger")
        logger.info("  - import_distribution_id: Optional import tracking ID")

    except Exception as e:
        logger.error(f"Error creating resource_distributions table: {e}")
        raise


if __name__ == "__main__":
    create_resource_distributions_table()

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


def create_distribution_types_table():
    """
    Create the distribution_types table for storing distribution type definitions.
    
    This table stores the reference types that can be used for resource distributions,
    based on the reference_types.csv data with renamed columns.
    """
    try:
        # Get database URL from environment and ensure it's synchronous
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api_test")
        sync_database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
        
        # Create engine
        engine = create_engine(sync_database_url)
        inspector = inspect(engine)

        logger.info("Creating distribution_types table...")

        with engine.connect() as conn:
            # Create the table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS distribution_types (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    distribution_type VARCHAR(255) NOT NULL,
                    distribution_uri VARCHAR(500) NOT NULL,
                    label BOOLEAN DEFAULT FALSE,
                    note TEXT,
                    position INTEGER DEFAULT 0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """))
            conn.execute(text("""
                ALTER TABLE distribution_types
                ALTER COLUMN created_at SET DEFAULT NOW(),
                ALTER COLUMN updated_at SET DEFAULT NOW();
            """))
            conn.execute(text("""
                UPDATE distribution_types
                SET
                    created_at = COALESCE(created_at, NOW()),
                    updated_at = COALESCE(updated_at, NOW())
                WHERE created_at IS NULL OR updated_at IS NULL;
            """))
            conn.commit()
        logger.info("✓ Table created")

        # Insert the reference types data
        logger.info("Inserting distribution types data...")
        with engine.connect() as conn:
            # Insert data from reference_types.csv
            distribution_types_data = [
                (1, 'arcgis_dynamic_map_layer', 'ArcGIS DynamicMapLayer', 'urn:x-esri:serviceType:ArcGIS#DynamicMapLayer', False, '-', 1),
                (2, 'arcgis_feature_layer', 'ArcGIS FeatureLayer', 'urn:x-esri:serviceType:ArcGIS#FeatureLayer', False, '-', 2),
                (3, 'arcgis_image_map_layer', 'ArcGIS ImageMapLayer', 'urn:x-esri:serviceType:ArcGIS#ImageMapLayer', False, '-', 3),
                (4, 'arcgis_tiled_map_layer', 'ArcGIS TiledMapLayer', 'urn:x-esri:serviceType:ArcGIS#TiledMapLayer', False, '-', 4),
                (5, 'cog', 'Cloud Optimized GeoTIFF (COG)', 'https://github.com/cogeotiff/cog-spec', False, '-', 5),
                (6, 'documentation_download', 'Data dictionary / supplemental documentation', 'http://lccn.loc.gov/sh85035852', False, 'Functions as a link to download documentation (not a viewer)', 6),
                (7, 'documentation_external', 'Documentation (External)', 'http://schema.org/url', False, '-', 7),
                (8, 'download', 'Download file', 'http://schema.org/downloadUrl', True, 'Link to download file (for multiple files see the multiple downloads guidelines)', 8),
                (9, 'geo_json', 'GeoJSON', 'http://geojson.org/geojson-spec.html', False, '-', 9),
                (11, 'iiif_image', 'International Image Interoperability Framework (IIIF) Image API', 'http://iiif.io/api/image', False, 'Load the image viewer using Leaflet-IIIF', 11),
                (12, 'iiif_manifest', 'International Image Interoperability Framework (IIIF) Presentation API Manifest', 'http://iiif.io/api/presentation#manifest', False, 'View the IIIF manifest - uses the Clover viewer by default https://samvera-labs.github.io/clover-iiif/docs', 12),
                (13, 'image', 'Image file', 'http://schema.org/image', True, '-', 13),
                (14, 'metadata_fgdc', 'Metadata in FGDC', 'http://www.opengis.net/cat/csw/csdgm', False, 'Provides an HTML view of an XML file in the FGDC standard', 14),
                (15, 'metadata_html', 'Metadata in HTML', 'http://www.w3.org/1999/xhtml', False, 'View structured metadata in any standard expressed as HTML', 15),
                (16, 'metadata_iso', 'Metadata in ISO 19139', 'http://www.isotc211.org/schemas/2005/gmd/', False, 'Provides an HTML view of an XML file in the ISO 19139 standard', 16),
                (17, 'metadata_mods', 'Metadata in MODS', 'http://www.loc.gov/mods/v3', False, 'Provides a raw XML view of metadata in the MODS format', 17),
                (18, 'oembed', 'oEmbed', 'https://oembed.com', False, '-', 18),
                (19, 'open_index_map', 'OpenIndexMap', 'https://openindexmaps.org', False, 'Provides an interactive preview of a GeoJSON file formatted as an OpenIndexMap', 19),
                (20, 'pmtiles', 'PMTiles', 'https://github.com/protomaps/PMTiles', False, '-', 20),
                (21, 'thumbnail', 'Thumbnail file', 'http://schema.org/thumbnailUrl', True, '-', 21),
                (22, 'tile_map_service', 'Tile Mapping Service (TMS)', 'https://wiki.osgeo.org/wiki/Tile_Map_Service_Specification', False, '-', 22),
                (23, 'tile_json', 'TileJSON', 'https://github.com/mapbox/tilejson-spec', False, '-', 23),
                (24, 'wcs', 'Web Coverage Service (WCS)', 'http://www.opengis.net/def/serviceType/ogc/wcs', False, '-', 24),
                (25, 'wfs', 'Web Feature Service (WFS)', 'http://www.opengis.net/def/serviceType/ogc/wfs', False, 'Provides a to download generated vector datasets (GeoJSON, shapefile)', 25),
                (26, 'wmts', 'Web Mapping Service (WMS)', 'http://www.opengis.net/def/serviceType/ogc/wms', False, 'Provides a service to visually preview a layer and inspect its features', 26),
                (27, 'wms', 'WMTS', 'http://www.opengis.net/def/serviceType/ogc/wmts', False, '-', 27),
                (28, 'xyz_tiles', 'XYZ tiles', 'https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames', False, 'Link to an XYZ tile server', 28)
            ]
            
            for data in distribution_types_data:
                conn.execute(text("""
                    INSERT INTO distribution_types (
                        id, name, distribution_type, distribution_uri, label, note, position,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :name, :distribution_type, :distribution_uri, :label, :note,
                        :position, NOW(), NOW()
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        distribution_type = EXCLUDED.distribution_type,
                        distribution_uri = EXCLUDED.distribution_uri,
                        label = EXCLUDED.label,
                        note = EXCLUDED.note,
                        position = EXCLUDED.position,
                        updated_at = NOW();
                """), {
                    'id': data[0],
                    'name': data[1],
                    'distribution_type': data[2],
                    'distribution_uri': data[3],
                    'label': data[4],
                    'note': data[5],
                    'position': data[6]
                })
            
            conn.commit()
        logger.info("✓ Distribution types data inserted")

        # Create indexes for fast querying
        logger.info("Creating indexes...")
        with engine.connect() as conn:
            # Index on name for lookups
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_distribution_types_name 
                ON distribution_types (name);
            """))
            
            # Index on distribution_uri for lookups
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_distribution_types_distribution_uri 
                ON distribution_types (distribution_uri);
            """))
            
            # Index on position for ordering
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_distribution_types_position 
                ON distribution_types (position);
            """))
            
            conn.commit()
        logger.info("✓ Indexes created")

        # Add trigger to update updated_at timestamp
        logger.info("Creating update trigger...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION update_distribution_types_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql';
            """))
            
            conn.execute(text("""
                DROP TRIGGER IF EXISTS trigger_update_distribution_types_updated_at 
                ON distribution_types;
            """))
            
            conn.execute(text("""
                CREATE TRIGGER trigger_update_distribution_types_updated_at
                    BEFORE UPDATE ON distribution_types
                    FOR EACH ROW
                    EXECUTE FUNCTION update_distribution_types_updated_at();
            """))
            
            conn.commit()
        logger.info("✓ Update trigger created")

        # Analyze the table
        logger.info("Updating table statistics...")
        with engine.connect() as conn:
            conn.execute(text("ANALYZE distribution_types;"))
            conn.commit()
        logger.info("✓ Table statistics updated")

        logger.info("🎉 distribution_types table created successfully!")
        logger.info("Table structure:")
        logger.info("  - id: Primary key")
        logger.info("  - name: Unique identifier for the distribution type")
        logger.info("  - distribution_type: Human-readable type name")
        logger.info("  - distribution_uri: URI/URL for the type specification")
        logger.info("  - label: Boolean indicating if this is a label type")
        logger.info("  - note: Additional notes about the type")
        logger.info("  - position: Ordering position")
        logger.info("  - created_at/updated_at: Timestamps with auto-update trigger")

    except Exception as e:
        logger.error(f"Error creating distribution_types table: {e}")
        raise


if __name__ == "__main__":
    create_distribution_types_table()

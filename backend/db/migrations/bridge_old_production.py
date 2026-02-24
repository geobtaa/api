import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy import create_engine, inspect, text

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# All fields from the resources table schema
RESOURCE_FIELDS = [
    # Core identification
    "id", "dct_title_s",
    
    # Descriptive fields
    "dct_alternative_sm", "dct_description_sm", "dct_language_sm", "gbl_displayNote_sm",
    
    # Creator and publisher
    "dct_creator_sm", "dct_publisher_sm", "schema_provider_s",
    
    # Classification
    "gbl_resourceClass_sm", "gbl_resourceType_sm",
    
    # Subject and themes
    "dct_subject_sm", "dcat_theme_sm", "dcat_keyword_sm",
    
    # Temporal
    "dct_temporal_sm", "dct_issued_s", "gbl_indexYear_im", "gbl_dateRange_drsim",
    
    # Spatial
    "dct_spatial_sm", "locn_geometry", "dcat_bbox", "dcat_centroid",
    
    # Relationships
    "dct_relation_sm", "pcdm_memberOf_sm", "dct_isPartOf_sm", "dct_source_sm",
    "dct_isVersionOf_sm", "dct_replaces_sm", "dct_isReplacedBy_sm",
    
    # Rights
    "dct_rights_sm", "dct_rightsHolder_sm", "dct_license_sm", "dct_accessRights_s",
    
    # Technical
    "dct_format_s", "gbl_fileSize_s", "gbl_wxsIdentifier_s", "dct_references_s",
    
    # Identifiers and metadata
    "dct_identifier_sm", "gbl_mdModified_dt", "gbl_mdVersion_s", "gbl_suppressed_b", "gbl_georeferenced_b",
    
    # BTAA-specific fields
    "b1g_code_s", "b1g_status_s", "b1g_dct_accrualMethod_s", "b1g_dct_accrualPeriodicity_s",
    "b1g_dateAccessioned_s", "b1g_dateAccessioned_sm", "b1g_dateRetired_s", "b1g_child_record_b", 
    "b1g_dct_mediator_sm", "b1g_access_s", "b1g_image_ss", "b1g_geonames_sm", 
    "b1g_publication_state_s", "b1g_language_sm", "b1g_creatorID_sm", "b1g_dct_conformsTo_sm",
    "b1g_dcat_spatialResolutionInMeters_sm", "b1g_geodcat_spatialResolutionAsText_sm",
    "b1g_dct_provenanceStatement_sm", "b1g_adminTags_sm",
    
    # Additional BTAA fields for migration
    "b1g_adms_supportedSchema_sm", "b1g_dcat_endpointDescription_s", "b1g_dcat_endpointURL_s",
    "b1g_dcat_inSeries_sm", "b1g_localCollectionLabel_sm", "b1g_prov_softwareAgent_sm",
    "b1g_prov_wasGeneratedBy_sm", "date_created_dtsi", "date_modified_dtsi", "geomg_id_s",
    "publication_state", "import_id",
    # BTAA latest-schema compatibility fields kept in the bridge view
    "b1g_adminNote_sm", "b1g_dateAccessioned_dt", "b1g_dateRetired_dt", "b1g_deprioritized_b",
    "b1g_harvestWorkflow_s", "b1g_isHarvested_b", "b1g_lastHarvested_dt", "b1g_dct_provenance_sm",
    "b1g_dcat_spatialResolutionInMeters_s", "b1g_websitePlatform_s",
]

# Field types for proper casting
ARRAY_FIELDS = {
    "dct_alternative_sm", "dct_description_sm", "dct_language_sm", "gbl_displayNote_sm",
    "dct_creator_sm", "dct_publisher_sm", "gbl_resourceClass_sm", "gbl_resourceType_sm",
    "dct_subject_sm", "dcat_theme_sm", "dcat_keyword_sm", "dct_temporal_sm",
    "gbl_indexYear_im", "gbl_dateRange_drsim", "dct_spatial_sm", "dct_relation_sm",
    "pcdm_memberOf_sm", "dct_isPartOf_sm", "dct_source_sm", "dct_isVersionOf_sm",
    "dct_replaces_sm", "dct_isReplacedBy_sm", "dct_rights_sm", "dct_rightsHolder_sm",
    "dct_license_sm", "dct_identifier_sm", "b1g_dct_mediator_sm", "b1g_geonames_sm",
    "b1g_language_sm", "b1g_creatorID_sm", "b1g_dct_conformsTo_sm",
    "b1g_dcat_spatialResolutionInMeters_sm", "b1g_geodcat_spatialResolutionAsText_sm",
    "b1g_dct_provenanceStatement_sm", "b1g_adminTags_sm",
    "b1g_dateAccessioned_sm", "b1g_adms_supportedSchema_sm", "b1g_dcat_inSeries_sm",
    "b1g_localCollectionLabel_sm", "b1g_prov_softwareAgent_sm", "b1g_prov_wasGeneratedBy_sm",
    "b1g_adminNote_sm", "b1g_dct_provenance_sm",
}

INTEGER_ARRAY_FIELDS = {
    "gbl_indexYear_im",
}

DATE_FIELDS = {
    "b1g_dateAccessioned_s", "b1g_dateRetired_s",
}

TIMESTAMP_FIELDS = {
    "gbl_mdModified_dt", "date_created_dtsi", "date_modified_dtsi",
    "b1g_dateAccessioned_dt", "b1g_dateRetired_dt", "b1g_lastHarvested_dt",
}

BOOLEAN_FIELDS = {
    "gbl_suppressed_b", "gbl_georeferenced_b", "b1g_child_record_b",
    "b1g_deprioritized_b", "b1g_isHarvested_b",
}

JSON_FIELDS = {
    "b1g_access_s",
}


def get_old_db_connection():
    """
    Get a connection to the old production database.
    
    Returns:
        sqlalchemy.engine.Engine: Database engine connected to old production DB
    """
    # Load environment variables
    old_db_name = os.getenv("OLD_DB_NAME", "geoportal_production_20251030")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "2345")
    
    # Construct connection URL for old database
    old_db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{old_db_name}"
    
    logger.info(f"Connecting to old production database: {old_db_name}")
    engine = create_engine(old_db_url)
    
    return engine


def generate_field_mapping_sql():
    """
    Generate the SQL SELECT clause for mapping json_attributes fields to resource table fields.
    
    Returns:
        str: SQL SELECT clause
    """
    mappings = []
    
    # Map friendlier_id to id (use friendlier_id if available, otherwise fallback to id)
    mappings.append("    COALESCE(friendlier_id::varchar, id::varchar)::varchar as \"id\"")
    
    # Map title directly from kithe_models.title
    mappings.append("    title as \"dct_title_s\"")
    
    # Map publication_state and import_id directly from kithe_models (not in json_attributes)
    mappings.append("    publication_state as \"publication_state\"")
    mappings.append("    import_id::varchar as \"import_id\"")
    
    # Map all other fields from json_attributes
    for field in RESOURCE_FIELDS:
        if field in ["id", "dct_title_s", "publication_state", "import_id"]:
            continue  # Already handled above
            
        json_key = field
        
        # Special compatibility mappings where old/new schema names differ.
        if field == "b1g_dct_provenance_sm":
            mapping = (
                "    ARRAY(SELECT jsonb_array_elements_text("
                "COALESCE(json_attributes->'b1g_dct_provenance_sm', json_attributes->'b1g_dct_provenanceStatement_sm')"
                ")) as \"b1g_dct_provenance_sm\""
            )
        elif field == "b1g_dcat_spatialResolutionInMeters_s":
            mapping = (
                "    COALESCE("
                "NULLIF(NULLIF(json_attributes->>'b1g_dcat_spatialResolutionInMeters_s', ''), 'null'), "
                "NULLIF(NULLIF((json_attributes->'b1g_dcat_spatialResolutionInMeters_sm'->>0), ''), 'null')"
                ") as \"b1g_dcat_spatialResolutionInMeters_s\""
            )
        elif field == "b1g_dateAccessioned_dt":
            mapping = (
                "    COALESCE("
                "NULLIF(NULLIF(json_attributes->>'b1g_dateAccessioned_dt', ''), 'null')::timestamp, "
                "NULLIF(NULLIF(json_attributes->>'b1g_dateAccessioned_s', ''), 'null')::date::timestamp"
                ") as \"b1g_dateAccessioned_dt\""
            )
        elif field == "b1g_dateRetired_dt":
            mapping = (
                "    COALESCE("
                "NULLIF(NULLIF(json_attributes->>'b1g_dateRetired_dt', ''), 'null')::timestamp, "
                "NULLIF(NULLIF(json_attributes->>'b1g_dateRetired_s', ''), 'null')::date::timestamp"
                ") as \"b1g_dateRetired_dt\""
            )
        # Determine JSON extraction operator and cast type based on field type
        # Use -> for JSONB fields (arrays, JSON) and ->> for scalar text fields
        elif field in INTEGER_ARRAY_FIELDS or field in ARRAY_FIELDS:
            # Array fields stored as JSON arrays, use jsonb_array_elements to convert
            if field in INTEGER_ARRAY_FIELDS:
                # For integer arrays, extract as text then cast to int
                mapping = f"    ARRAY(SELECT (jsonb_array_elements_text(json_attributes->'{json_key}'))::integer) as \"{field}\""
            else:
                # For text arrays
                mapping = f"    ARRAY(SELECT jsonb_array_elements_text(json_attributes->'{json_key}')) as \"{field}\""
        elif field in JSON_FIELDS:
            # JSON fields: keep JSON objects/arrays as-is and normalize string/null-ish values safely.
            # Avoid comparing jsonb directly to text (invalid operator in Postgres).
            mapping = (
                f"    CASE "
                f"WHEN json_attributes->'{json_key}' IS NULL OR json_attributes->'{json_key}' = 'null'::jsonb THEN NULL "
                f"WHEN jsonb_typeof(json_attributes->'{json_key}') = 'string' THEN "
                f"  CASE "
                f"    WHEN NULLIF(NULLIF(json_attributes->>'{json_key}', ''), 'null') IS NULL THEN NULL "
                f"    ELSE to_jsonb(json_attributes->>'{json_key}') "
                f"  END "
                f"ELSE json_attributes->'{json_key}' "
                f"END as \"{field}\""
            )
        else:
            # Scalar fields, use ->> to get text value
            json_op = "->>"
            if field in DATE_FIELDS:
                cast_type = "::date"
                mapping = f"    NULLIF(NULLIF(json_attributes{json_op}'{json_key}', ''), 'null'){cast_type} as \"{field}\""
            elif field in TIMESTAMP_FIELDS:
                cast_type = "::timestamp"
                mapping = f"    NULLIF(NULLIF(json_attributes{json_op}'{json_key}', ''), 'null'){cast_type} as \"{field}\""
            elif field in BOOLEAN_FIELDS:
                cast_type = "::boolean"
                mapping = f"    NULLIF(NULLIF(json_attributes{json_op}'{json_key}', ''), 'null'){cast_type} as \"{field}\""
            else:
                cast_type = ""  # No cast for varchar/text fields
                mapping = f"    (json_attributes{json_op}'{json_key}'){cast_type} as \"{field}\""
        
        mappings.append(mapping)
    
    return ",\n".join(mappings)


def create_materialized_view():
    """
    Create a materialized view in the old database that transforms kithe_models records
    to match the new resources table schema.
    """
    logger.info("Creating materialized view in old production database...")
    
    try:
        engine = get_old_db_connection()
        
        # Generate the field mapping SQL
        field_mappings = generate_field_mapping_sql()
        
        # Create the materialized view
        create_view_sql = f"""
        DROP MATERIALIZED VIEW IF EXISTS kithe_to_resources_bridge CASCADE;
        
        CREATE MATERIALIZED VIEW kithe_to_resources_bridge AS
        SELECT
{field_mappings}
        FROM kithe_models 
        WHERE type = 'Document' AND publication_state = 'published';
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_view_sql))
            conn.commit()
        
        logger.info("✓ Materialized view created successfully")
        
        # Create an index on the materialized view
        logger.info("Creating index on materialized view...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_kithe_to_resources_bridge_id 
                ON kithe_to_resources_bridge (id);
            """))
            conn.commit()
        logger.info("✓ Index created")
        
        # Refresh the view to populate data
        logger.info("Refreshing materialized view...")
        with engine.connect() as conn:
            conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY kithe_to_resources_bridge;"))
            conn.commit()
        logger.info("✓ Materialized view refreshed")
        
        # Get count
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM kithe_to_resources_bridge;"))
            count = result.scalar()
            logger.info(f"✓ Materialized view contains {count:,} records")
        
    except Exception as e:
        logger.error(f"Error creating materialized view: {e}")
        raise


def sample_json_attributes(limit: int = 5) -> List[Dict[str, Any]]:
    """
    Sample some records from kithe_models to inspect the JSON attributes structure.
    
    Args:
        limit: Number of records to sample
        
    Returns:
        List of dictionaries containing sampled records
    """
    logger.info(f"Sampling {limit} records from kithe_models to inspect JSON structure...")
    
    try:
        engine = get_old_db_connection()
        
        with engine.connect() as conn:
            result = conn.execute(text(f"""
                SELECT id, title, type, json_attributes
                FROM kithe_models 
                WHERE type = 'Document'
                LIMIT {limit};
            """))
            
            records = []
            for row in result:
                records.append({
                    'id': row[0],
                    'title': row[1],
                    'type': row[2],
                    'json_attributes': row[3]
                })
            
            return records
            
    except Exception as e:
        logger.error(f"Error sampling records: {e}")
        raise


def verify_field_mapping():
    """
    Sample records and verify that JSON keys match expected schema fields.
    Reports any mismatches or missing fields.
    """
    logger.info("Verifying field mapping...")
    
    try:
        # Sample records
        samples = sample_json_attributes(limit=10)
        
        if not samples:
            logger.warning("No samples found in kithe_models table")
            return
        
        # Collect all JSON keys from sampled records
        all_json_keys = set()
        for sample in samples:
            if sample['json_attributes']:
                all_json_keys.update(sample['json_attributes'].keys())
        
        logger.info(f"Found {len(all_json_keys)} unique JSON keys in sampled records")
        
        # Check which JSON keys map to resource fields
        matching_keys = []
        unmapped_keys = []
        
        for key in all_json_keys:
            if key in RESOURCE_FIELDS:
                matching_keys.append(key)
            else:
                unmapped_keys.append(key)
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Field Mapping Verification Results")
        logger.info(f"{'='*80}")
        logger.info(f"Total JSON keys found: {len(all_json_keys)}")
        logger.info(f"Keys matching new schema: {len(matching_keys)}")
        logger.info(f"Unmapped keys: {len(unmapped_keys)}")
        
        if matching_keys:
            logger.info(f"\n✓ Matching fields ({len(matching_keys)}):")
            for key in sorted(matching_keys):
                logger.info(f"  - {key}")
        
        if unmapped_keys:
            logger.warning(f"\n⚠ Unmapped fields ({len(unmapped_keys)}):")
            for key in sorted(unmapped_keys):
                logger.warning(f"  - {key}")
        
        # Check for new schema fields not present in old data
        missing_keys = set(RESOURCE_FIELDS) - all_json_keys - {"id", "dct_title_s"}
        if missing_keys:
            logger.info(f"\nℹ New schema fields not in old data ({len(missing_keys)}):")
            for key in sorted(missing_keys):
                logger.info(f"  - {key}")
        
        logger.info(f"{'='*80}\n")
        
    except Exception as e:
        logger.error(f"Error verifying field mapping: {e}")
        raise


def export_transformed_data(output_path: Optional[str] = None):
    """
    Export the materialized view data to a file.
    
    Args:
        output_path: Optional path to save exported data. Defaults to timestamped file in tmp/
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"tmp/kithe_to_resources_bridge_{timestamp}.json"
    
    logger.info(f"Exporting transformed data to {output_path}...")
    
    try:
        engine = get_old_db_connection()
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with engine.connect() as conn:
            # Get all records
            result = conn.execute(text("SELECT * FROM kithe_to_resources_bridge;"))
            
            # Write to file as JSON lines
            import json
            with open(output_path, 'w') as f:
                for row in result:
                    # Convert row to dict
                    record = dict(row._mapping)
                    # Write as JSON line
                    f.write(json.dumps(record) + '\n')
        
        # Get file size
        file_size = os.path.getsize(output_path)
        logger.info(f"✓ Export complete: {output_path} ({file_size:,} bytes)")
        
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise


def get_view_summary():
    """
    Get a summary of the materialized view including record count and sample data.
    """
    logger.info("Getting materialized view summary...")
    
    try:
        engine = get_old_db_connection()
        
        with engine.connect() as conn:
            # Get count
            result = conn.execute(text("SELECT COUNT(*) FROM kithe_to_resources_bridge;"))
            count = result.scalar()
            logger.info(f"Total records: {count:,}")
            
            # Get a few sample IDs
            result = conn.execute(text("SELECT id, dct_title_s FROM kithe_to_resources_bridge LIMIT 5;"))
            logger.info("\nSample records:")
            for row in result:
                logger.info(f"  - {row[0]}: {row[1][:60]}..." if row[1] and len(row[1]) > 60 else f"  - {row[0]}: {row[1]}")
            
    except Exception as e:
        logger.error(f"Error getting view summary: {e}")
        raise


def main():
    """
    Main entry point for the bridge script.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Bridge old production database to new schema')
    parser.add_argument('--verify', action='store_true', help='Verify field mapping without creating view')
    parser.add_argument('--create-view', action='store_true', help='Create the materialized view')
    parser.add_argument('--refresh', action='store_true', help='Refresh the materialized view')
    parser.add_argument('--export', type=str, help='Export data to file (JSON lines format)')
    parser.add_argument('--summary', action='store_true', help='Show summary of materialized view')
    parser.add_argument('--sample', type=int, default=5, help='Number of samples for verification (default: 5)')
    
    args = parser.parse_args()
    
    # If no specific action, run verify and create-view
    if not any([args.verify, args.create_view, args.refresh, args.export, args.summary]):
        logger.info("No specific action specified. Running verification and creating view...")
        verify_field_mapping()
        create_materialized_view()
        get_view_summary()
        return
    
    if args.verify:
        verify_field_mapping()
    
    if args.create_view:
        create_materialized_view()
    
    if args.refresh:
        logger.info("Refreshing materialized view...")
        try:
            engine = get_old_db_connection()
            with engine.connect() as conn:
                conn.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY kithe_to_resources_bridge;"))
                conn.commit()
            logger.info("✓ Materialized view refreshed")
        except Exception as e:
            logger.error(f"Error refreshing view: {e}")
            raise
    
    if args.export:
        export_transformed_data(args.export)
    
    if args.summary:
        get_view_summary()


if __name__ == "__main__":
    main()


import logging
import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_old_db_connection():
    """
    Get a connection to the old production database.
    
    Returns:
        sqlalchemy.engine.Engine: Database engine connected to old production DB
    """
    old_db_name = os.getenv("OLD_DB_NAME", "geoportal_production_20251030")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "2345")
    
    old_db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{old_db_name}"
    logger.info(f"Connecting to old production database: {old_db_name}")
    engine = create_engine(old_db_url)
    
    return engine


def get_new_db_connection():
    """
    Get a connection to the new production database.
    
    Returns:
        sqlalchemy.engine.Engine: Database engine connected to new production DB
    """
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "2345")
    db_name = os.getenv("DB_NAME", "btaa_ogm_api")
    
    new_db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    logger.info(f"Connecting to new production database: {db_name}")
    engine = create_engine(new_db_url)
    
    return engine


def validate_materialized_view():
    """
    Verify that the materialized view exists in the old database.
    
    Returns:
        bool: True if view exists, False otherwise
    """
    logger.info("Validating materialized view exists...")
    
    try:
        engine = get_old_db_connection()
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM pg_matviews 
                    WHERE matviewname = 'kithe_to_resources_bridge'
                );
            """))
            exists = result.scalar()
            
            if not exists:
                logger.error("Materialized view 'kithe_to_resources_bridge' does not exist")
                logger.error("Please run: python db/migrations/bridge_old_production.py --create-view")
                return False
            
            # Get count
            result = conn.execute(text("SELECT COUNT(*) FROM kithe_to_resources_bridge;"))
            count = result.scalar()
            logger.info(f"✓ Materialized view exists with {count:,} records")
            
            return True
            
    except Exception as e:
        logger.error(f"Error validating materialized view: {e}")
        return False


def get_resource_column_names():
    """
    Get all column names from the resources table in the new database.
    
    Returns:
        List[str]: List of column names
    """
    logger.info("Getting resource table column names...")
    
    try:
        engine = get_new_db_connection()
        inspector = inspect(engine)
        
        # Check if table exists
        if not inspector.has_table("resources"):
            logger.error("Resources table does not exist in new database")
            return []
        
        columns = inspector.get_columns("resources")
        column_names = [col['name'] for col in columns]
        
        logger.info(f"✓ Found {len(column_names)} columns in resources table")
        return column_names
        
    except Exception as e:
        logger.error(f"Error getting column names: {e}")
        return []


def get_json_column_names():
    """
    Get column names that have JSON type in the resources table.
    
    Returns:
        List[str]: List of JSON column names
    """
    try:
        engine = get_new_db_connection()
        inspector = inspect(engine)
        
        columns = inspector.get_columns("resources")
        json_columns = []
        for col in columns:
            # Check if the column type is JSON or JSONB
            col_type = str(col['type'])
            if 'JSON' in col_type.upper() or 'JSONB' in col_type.upper():
                json_columns.append(col['name'])
        
        return json_columns
        
    except Exception as e:
        logger.error(f"Error getting JSON column names: {e}")
        return []


def import_data(dry_run: bool = False, batch_size: int = 1000, conflict_action: str = "skip"):
    """
    Import data from the materialized view in old database to new database.
    
    Args:
        dry_run: If True, only simulate the import without writing data
        batch_size: Number of records to process per batch
        conflict_action: How to handle conflicts ("skip", "update", "fail")
    """
    logger.info(f"Starting data import (dry_run={dry_run}, batch_size={batch_size}, conflict_action={conflict_action})...")
    
    # Validate materialized view exists
    if not validate_materialized_view():
        return
    
    # Get column names from new database
    new_columns = get_resource_column_names()
    if not new_columns:
        logger.error("Cannot proceed without column names")
        return
    
    # Get JSON column names for handling empty strings
    json_columns = get_json_column_names()
    logger.info(f"Found {len(json_columns)} JSON columns")
    
    try:
        old_engine = get_old_db_connection()
        new_engine = get_new_db_connection()
        
        # Get total count
        with old_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM kithe_to_resources_bridge;"))
            total_count = result.scalar()
        
        logger.info(f"Processing {total_count:,} records in batches of {batch_size}...")
        
        # Process in batches
        offset = 0
        imported_count = 0
        skipped_count = 0
        error_count = 0
        errors = []
        
        while offset < total_count:
            # Fetch batch from old database
            logger.info(f"Fetching batch: offset={offset:,}, limit={batch_size}")
            
            with old_engine.connect() as old_conn:
                result = old_conn.execute(text(f"""
                    SELECT * FROM kithe_to_resources_bridge
                    LIMIT {batch_size} OFFSET {offset};
                """))
                
                batch_records = []
                for row in result:
                    record = dict(row._mapping)
                    # Convert empty strings to None for JSON columns
                    for json_col in json_columns:
                        if json_col in record and record[json_col] == '':
                            record[json_col] = None
                    batch_records.append(record)
            
            if not batch_records:
                break
            
            # Import batch to new database
            if not dry_run:
                batch_imported, batch_skipped, batch_errors = _import_batch(
                    new_engine, batch_records, new_columns, conflict_action
                )
                imported_count += batch_imported
                skipped_count += batch_skipped
                error_count += len(batch_errors)
                errors.extend(batch_errors)
            else:
                logger.info(f"[DRY RUN] Would import {len(batch_records)} records")
            
            offset += batch_size
            progress_pct = (offset / total_count) * 100 if total_count > 0 else 0
            logger.info(f"Progress: {min(offset, total_count):,}/{total_count:,} ({progress_pct:.1f}%)")
        
        # Print summary
        logger.info(f"\n{'='*80}")
        logger.info(f"Import Summary")
        logger.info(f"{'='*80}")
        logger.info(f"Total records: {total_count:,}")
        if not dry_run:
            logger.info(f"Imported: {imported_count:,}")
            logger.info(f"Skipped: {skipped_count:,}")
            logger.info(f"Errors: {error_count:,}")
        else:
            logger.info(f"[DRY RUN] Would have processed: {total_count:,}")
        logger.info(f"{'='*80}\n")
        
        # Print errors if any
        if errors:
            logger.warning(f"\nFirst 10 errors:")
            for i, error in enumerate(errors[:10]):
                logger.warning(f"  {i+1}. {error}")
            if len(errors) > 10:
                logger.warning(f"  ... and {len(errors) - 10} more errors")
        
    except Exception as e:
        logger.error(f"Error during import: {e}")
        raise


def _import_batch(engine, records: List[Dict], column_names: List[str], conflict_action: str) -> tuple:
    """
    Import a batch of records to the new database.
    
    Args:
        engine: Database engine for new database
        records: List of record dictionaries
        column_names: List of column names in the target table
        conflict_action: How to handle conflicts
        
    Returns:
        Tuple of (imported_count, skipped_count, errors_list)
    """
    imported_count = 0
    skipped_count = 0
    errors = []
    
    # Filter records to only include columns that exist in target table
    filtered_records = []
    for record in records:
        filtered_record = {k: v for k, v in record.items() if k in column_names}
        filtered_records.append(filtered_record)
    
    # Quote all column names to preserve mixed-case identifiers
    quoted_columns = [f'"{col}"' for col in column_names]
    
    # Build INSERT statement based on conflict action
    if conflict_action == "skip":
        # Use INSERT ... ON CONFLICT DO NOTHING
        insert_sql = f"""
            INSERT INTO resources ({', '.join(quoted_columns)})
            VALUES ({', '.join([':' + col for col in column_names])})
            ON CONFLICT ("id") DO NOTHING;
        """
    elif conflict_action == "update":
        # Use INSERT ... ON CONFLICT DO UPDATE
        update_clause = ', '.join([f'"{col}" = EXCLUDED."{col}"' for col in column_names if col != 'id'])
        insert_sql = f"""
            INSERT INTO resources ({', '.join(quoted_columns)})
            VALUES ({', '.join([':' + col for col in column_names])})
            ON CONFLICT ("id") DO UPDATE SET {update_clause};
        """
    else:  # fail
        # Use regular INSERT (will fail on conflict)
        insert_sql = f"""
            INSERT INTO resources ({', '.join(quoted_columns)})
            VALUES ({', '.join([':' + col for col in column_names])});
        """
    
    # Execute batch import
    try:
        with engine.connect() as conn:
            # Use execute many for better performance
            result = conn.execute(text(insert_sql), filtered_records)
            conn.commit()
            
            if hasattr(result, 'rowcount'):
                imported_count = result.rowcount
            else:
                imported_count = len(filtered_records)
                
    except IntegrityError as e:
        if conflict_action == "fail":
            errors.append(f"Integrity error: {str(e)}")
        # For skip/update, individual failures are handled by DO NOTHING/UPDATE
    except Exception as e:
        errors.append(f"Error importing batch: {str(e)}")
    
    return imported_count, skipped_count, errors


def verify_import():
    """
    Verify the imported data by comparing counts and sampling records.
    """
    logger.info("Verifying imported data...")
    
    try:
        old_engine = get_old_db_connection()
        new_engine = get_new_db_connection()
        
        # Get counts
        with old_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM kithe_to_resources_bridge;"))
            old_count = result.scalar()
        
        with new_engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM resources;"))
            new_count = result.scalar()
        
        logger.info(f"\n{'='*80}")
        logger.info(f"Import Verification")
        logger.info(f"{'='*80}")
        logger.info(f"Old database records: {old_count:,}")
        logger.info(f"New database records: {new_count:,}")
        
        # Sample some records for comparison
        logger.info("\nSampling records for comparison...")
        with old_engine.connect() as conn:
            result = conn.execute(text("SELECT id, dct_title_s FROM kithe_to_resources_bridge LIMIT 10;"))
            old_samples = [(row[0], row[1]) for row in result]
        
        with new_engine.connect() as conn:
            # Build a WHERE clause for the sampled IDs
            ids = [sample[0] for sample in old_samples]
            placeholders = ', '.join([f"'{id}'" for id in ids])
            result = conn.execute(text(f"SELECT id, dct_title_s FROM resources WHERE id IN ({placeholders});"))
            new_samples = {(row[0], row[1]) for row in result}
        
        # Compare
        matching = 0
        for old_sample in old_samples:
            if old_sample in new_samples:
                matching += 1
        
        logger.info(f"Sample comparison: {matching}/{len(old_samples)} records match")
        
        if matching == len(old_samples):
            logger.info("✓ All sampled records imported successfully")
        else:
            logger.warning(f"⚠ Only {matching}/{len(old_samples)} sampled records found")
        
        logger.info(f"{'='*80}\n")
        
    except Exception as e:
        logger.error(f"Error verifying import: {e}")
        raise


def main():
    """
    Main entry point for the import script.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Import data from old production database')
    parser.add_argument('--dry-run', action='store_true', help='Simulate import without writing data')
    parser.add_argument('--batch-size', type=int, default=1000, help='Number of records per batch (default: 1000)')
    parser.add_argument('--conflict', choices=['skip', 'update', 'fail'], default='skip',
                      help='How to handle ID conflicts: skip, update, or fail (default: skip)')
    parser.add_argument('--verify', action='store_true', help='Verify the import after running')
    
    args = parser.parse_args()
    
    # Run import
    import_data(dry_run=args.dry_run, batch_size=args.batch_size, conflict_action=args.conflict)
    
    # Verify if requested
    if args.verify and not args.dry_run:
        verify_import()


if __name__ == "__main__":
    main()


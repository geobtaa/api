#!/usr/bin/env python3
"""
Migration to update database column names to use proper OGM field names.

This migration renames columns from downcased versions to proper OGM Aardvark field names.
"""

import os
import sys
from pathlib import Path

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def update_ogm_field_names():
    """Update database column names to use proper OGM field names."""
    
    # Get database URL from environment
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api"
    )
    
    # Convert async URL to sync URL
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    engine = create_engine(database_url)
    
    # Mapping from current (downcased) column names to proper OGM field names
    column_mappings = {
        # Standard OGM Aardvark fields
        "gbl_mdversion_s": "gbl_mdVersion_s",
        "gbl_mdmodified_dt": "gbl_mdModified_dt", 
        "gbl_resourceclass_sm": "gbl_resourceClass_sm",
        "gbl_resourcetype_sm": "gbl_resourceType_sm",
        "gbl_indexyear_im": "gbl_indexYear_im",
        "gbl_daterange_drsim": "gbl_dateRange_drsim",
        "gbl_filesize_s": "gbl_fileSize_s",
        "gbl_wxsidentifier_s": "gbl_wxsIdentifier_s",
        "gbl_displaynote_sm": "gbl_displayNote_sm",
        
        # BTAA-specific fields
        "b1g_dct_accrualmethod_s": "b1g_dct_accrualMethod_s",
        "b1g_dct_accrualperiodicity_s": "b1g_dct_accrualPeriodicity_s",
        "b1g_dateaccessioned_s": "b1g_dateAccessioned_s",
        "b1g_dateretired_s": "b1g_dateRetired_s",
        "b1g_creatorid_sm": "b1g_creatorID_sm",
        "b1g_dct_conformsto_sm": "b1g_dct_conformsTo_sm",
        "b1g_dcat_spatialresolutioninmeters_sm": "b1g_dcat_spatialResolutionInMeters_sm",
        "b1g_geodcat_spatialresolutionastext_sm": "b1g_geodcat_spatialResolutionAsText_sm",
        "b1g_dct_provenancestatement_sm": "b1g_dct_provenanceStatement_sm",
        "b1g_admintags_sm": "b1g_adminTags_sm",
        
        # Other fields that might be downcased
        "dct_accessrights_s": "dct_accessRights_s",
        "dct_rightsholder_sm": "dct_rightsHolder_sm",
        "dct_ispartof_sm": "dct_isPartOf_sm",
        "dct_isversionof_sm": "dct_isVersionOf_sm",
        "dct_isreplacedby_sm": "dct_isReplacedBy_sm",
        "pcdm_memberof_sm": "pcdm_memberOf_sm",
    }
    
    print("Starting database schema update to use proper OGM field names...")
    
    with engine.connect() as conn:
        # Start a transaction
        trans = conn.begin()
        
        try:
            for old_column, new_column in column_mappings.items():
                print(f"Renaming column {old_column} to {new_column}...")
                
                # Check if the old column exists
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'resources' 
                    AND column_name = :old_column
                """), {"old_column": old_column})
                
                if result.fetchone():
                    # Check if the new column already exists
                    result_new = conn.execute(text("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'resources' 
                        AND column_name = :new_column
                    """), {"new_column": new_column})
                    
                    if result_new.fetchone():
                        print(f"  ⚠ Column {new_column} already exists, skipping rename of {old_column}")
                    else:
                        # Rename the column
                        conn.execute(text(f"""
                            ALTER TABLE resources 
                            RENAME COLUMN "{old_column}" TO "{new_column}"
                        """))
                        print(f"  ✓ Renamed {old_column} to {new_column}")
                else:
                    print(f"  ⚠ Column {old_column} not found, skipping...")
            
            # Commit the transaction
            trans.commit()
            print("\n✓ Database schema update completed successfully!")
            
        except Exception as e:
            # Rollback on error
            trans.rollback()
            print(f"\n✗ Error updating database schema: {e}")
            raise


def verify_schema_update():
    """Verify that the schema update was successful."""
    
    # Get database URL from environment
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:2345/btaa_ogm_api"
    )
    
    # Convert async URL to sync URL
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
    
    engine = create_engine(database_url)
    
    print("\nVerifying schema update...")
    
    with engine.connect() as conn:
        # Get all column names from the resources table
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'resources' 
            ORDER BY column_name
        """))
        
        columns = [row[0] for row in result.fetchall()]
        
        # Check for key OGM field names
        expected_columns = [
            "gbl_mdVersion_s",
            "gbl_resourceClass_sm", 
            "gbl_resourceType_sm",
            "gbl_indexYear_im",
            "dct_accessRights_s",
            "dct_rightsHolder_sm"
        ]
        
        print("\nColumn verification:")
        for expected_col in expected_columns:
            if expected_col in columns:
                print(f"  ✓ {expected_col}")
            else:
                print(f"  ✗ {expected_col} - MISSING")
        
        print(f"\nTotal columns in resources table: {len(columns)}")


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Update OGM field names in database")
    parser.add_argument("--verify-only", action="store_true", 
                       help="Only verify the current schema, don't make changes")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose output")
    
    args = parser.parse_args()
    
    if args.verify_only:
        verify_schema_update()
    else:
        update_ogm_field_names()
        verify_schema_update()


if __name__ == "__main__":
    main()

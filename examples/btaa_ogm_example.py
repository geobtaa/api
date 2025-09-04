#!/usr/bin/env python3
"""
Example of BTAA flavored OGM Aardvark record processing.

This script demonstrates how the system processes BTAA records,
including field mapping from database column names to proper OGM field names.
"""

import sys
from pathlib import Path

# Add the project root directory to Python path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.ogm_field_mapper import OGMFieldMapper


def demonstrate_btaa_processing():
    """Demonstrate BTAA OGM Aardvark record processing."""
    
    print("🌍 BTAA OGM Aardvark Record Processing Example")
    print("=" * 60)
    
    # Simulate a database response with downcased field names
    # This is what would come back from the database
    db_resource = {
        "id": "02236876-9c21-42f6-9870-d2562da8e44f",
        "gbl_mdversion_s": "Aardvark",
        "gbl_mdmodified_dt": "2021-06-01T22:14:16",
        "schema_provider_s": "University of Minnesota",
        "dct_title_s": "2030 Regional Development Framework Planning Areas: Metro Twin Cities, Minnesota, 2011",
        "dct_alternative_sm": ["umn_metro_result1"],
        "dct_description_sm": [
            "Bounding box of metropolitan area and ArcGIS Dynamic Feature Service.",
            "The 2030 Regional Development Framework Planning Areas - 2011 updates the 2030 Regional Development Framework Planning Areas initially adopted on January 14, 2004 and ammended in 2006."
        ],
        "dct_subject_sm": ["Property"],
        "dct_creator_sm": ["Metropolitan Council"],
        "dct_publisher_sm": ["Metropolitan Council"],
        "dct_language_sm": ["eng"],
        "dct_license_sm": ["http://creativecommons.org/publicdomain/zero/1.0/"],
        "dct_accessrights_s": "Public",
        "gbl_resourceclass_sm": ["Datasets", "Web services"],
        "gbl_resourcetype_sm": ["Polygon data"],
        "dct_source_sm": ["GBL Fixture records"],
        "dct_ispartof_sm": ["GBL Fixture records"],
        "dct_issued_s": "2015-10-01",
        "dct_temporal_sm": ["2014", "2030"],
        "dct_spatial_sm": ["Minnesota"],
        "dcat_bbox": "ENVELOPE(-94.012,-92.732,45.415,44.471)",
        "dcat_centroid": "44.943,-93.372",
        "locn_geometry": "ENVELOPE(-94.012,-92.732,45.415,44.471)",
        "layer_geom_type_s": "Polygon",
        "solr_year_i": 2014,
        "layer_id_s": "umn_metro_result1",
        "suppressed_b": False,
        "dct_references_s": '{"http://schema.org/downloadUrl":"ftp://ftp.gisdata.mn.gov/pub/gdrs/data/pub/us_mn_state_metc/plan_frmwrk2030dev_plan_ar2011/shp_plan_frmwrk2030dev_plan_ar2011.zip","urn:x-esri:serviceType:ArcGIS#FeatureLayer":"https://arcgis.metc.state.mn.us/server/rest/services/GISLibrary/Framework2030PlanningAreas2011/FeatureServer/0","http://schema.org/url":"https://gisdata.mn.gov/dataset/02236876-9c21-42f6-9870-d2562da8e44f"}',
        
        # BTAA-specific fields (these would be added by the migration)
        "b1g_code_s": "UMN-METRO-001",
        "b1g_status_s": "active",
        "b1g_dct_accrualmethod_s": "periodic",
        "b1g_dct_accrualperiodicity_s": "annual",
        "b1g_dateaccessioned_s": "2021-06-01",
        "b1g_dateretired_s": None,
        "b1g_child_record_b": False,
        "b1g_dct_mediator_sm": ["Metropolitan Council GIS Staff"],
        "b1g_access_s": {
            "public": "https://gisdata.mn.gov/dataset/02236876-9c21-42f6-9870-d2562da8e44f",
            "restricted": "https://arcgis.metc.state.mn.us/server/rest/services/GISLibrary/Framework2030PlanningAreas2011/FeatureServer/0"
        },
        "b1g_image_ss": "https://gisdata.mn.gov/dataset/02236876-9c21-42f6-9870-d2562da8e44f/preview",
        "b1g_geonames_sm": ["https://sws.geonames.org/5037779/"],
        "b1g_publication_state_s": "published",
        "b1g_language_sm": ["eng"],
        "b1g_creatorid_sm": ["https://orcid.org/0000-0000-0000-0000"],
        "b1g_dct_conformsto_sm": ["https://opengeometadata.github.io/aardvark/aardvarkMetadata.html"],
        "b1g_dcat_spatialresolutioninmeters_sm": ["30"],
        "b1g_geodcat_spatialresolutionastext_sm": ["30 meters"],
        "b1g_dct_provenancestatement_sm": ["Data provided by Metropolitan Council GIS staff"],
        "b1g_admintags_sm": ["planning", "development", "metro", "twin-cities"]
    }
    
    print("\n📊 Database Response (with downcased field names):")
    print("-" * 50)
    for key, value in list(db_resource.items())[:10]:  # Show first 10 fields
        print(f"  {key}: {value}")
    print("  ... (truncated)")
    
    # Apply OGM field mapping
    mapped_resource = OGMFieldMapper.map_resource_fields(db_resource)
    
    print("\n🔄 After OGM Field Mapping:")
    print("-" * 50)
    for key, value in list(mapped_resource.items())[:10]:  # Show first 10 fields
        print(f"  {key}: {value}")
    print("  ... (truncated)")
    
    # Show specific examples of field mapping
    print("\n🔍 Field Mapping Examples:")
    print("-" * 50)
    mapping_examples = [
        ("gbl_mdversion_s", "gbl_mdVersion_s"),
        ("gbl_resourceclass_sm", "gbl_resourceClass_sm"),
        ("gbl_resourcetype_sm", "gbl_resourceType_sm"),
        ("dct_accessrights_s", "dct_accessRights_s"),
        ("b1g_dct_accrualmethod_s", "b1g_dct_accrualMethod_s"),
        ("b1g_dateaccessioned_s", "b1g_dateAccessioned_s"),
    ]
    
    for db_field, ogm_field in mapping_examples:
        if db_field in db_resource:
            print(f"  {db_field} → {ogm_field}")
            print(f"    Value: {db_resource[db_field]}")
    
    # Show BTAA-specific fields
    print("\n🏛️ BTAA-Specific Fields:")
    print("-" * 50)
    btaa_fields = [key for key in mapped_resource.keys() if key.startswith("b1g_")]
    for field in btaa_fields[:5]:  # Show first 5 BTAA fields
        print(f"  {field}: {mapped_resource[field]}")
    print("  ... (truncated)")
    
    # Validate required fields
    print("\n✅ Required Fields Validation:")
    print("-" * 50)
    required_fields = OGMFieldMapper.get_required_fields()
    missing_fields = []
    
    for field in required_fields:
        if field in mapped_resource and mapped_resource[field] is not None:
            print(f"  ✅ {field}: Present")
        else:
            print(f"  ❌ {field}: Missing or null")
            missing_fields.append(field)
    
    if missing_fields:
        print(f"\n⚠️  Missing required fields: {', '.join(missing_fields)}")
    else:
        print("\n🎉 All required fields are present!")
    
    print("\n" + "=" * 60)
    print("This example demonstrates how the system:")
    print("1. Receives database records with downcased field names")
    print("2. Maps them to proper OGM Aardvark field names")
    print("3. Supports BTAA-specific extensions to the schema")
    print("4. Validates compliance with the BTAA OGM Aardvark schema")


if __name__ == "__main__":
    demonstrate_btaa_processing()

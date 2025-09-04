# BTAA OGM Aardvark Implementation

This document describes the implementation of BTAA flavored OGM Aardvark record support in the data API.

## Overview

The system now properly supports BTAA flavored OGM Aardvark records, which extend the standard OpenGeoMetadata Aardvark schema with BTAA-specific elements. The key challenge addressed is that the database downcases most element names as column names, so we get `gbl_resourceclass_sm` back from the database instead of `gbl_resourceClass_sm`.

## Architecture

### 1. OGM Field Mapper Service

The `OGMFieldMapper` service (`app/services/ogm_field_mapper.py`) handles the mapping between database column names and proper OGM field names.

**Key Features:**
- Maps downcased database fields to proper OGM field names
- Supports all BTAA-specific extensions
- Provides validation methods for required fields
- Maintains backward compatibility

**Example Mapping:**
```python
# Database returns:
"gbl_resourceclass_sm": ["Datasets"]

# Mapper converts to:
"gbl_resourceClass_sm": ["Datasets"]
```

### 2. Database Schema Updates

The `resources` table has been extended with BTAA-specific fields:

```sql
-- BTAA-specific fields for OGM Aardvark compliance
b1g_code_s VARCHAR,
b1g_status_s VARCHAR,
b1g_dct_accrualmethod_s VARCHAR,
b1g_dct_accrualperiodicity_s VARCHAR,
b1g_dateaccessioned_s DATE,
b1g_dateretired_s DATE,
b1g_child_record_b BOOLEAN,
b1g_dct_mediator_sm VARCHAR[],
b1g_access_s JSONB,
b1g_image_ss VARCHAR,
b1g_geonames_sm VARCHAR[],
b1g_publication_state_s VARCHAR,
b1g_language_sm VARCHAR[],
b1g_creatorid_sm VARCHAR[],
b1g_dct_conformsto_sm VARCHAR[],
b1g_dcat_spatialresolutioninmeters_sm VARCHAR[],
b1g_geodcat_spatialresolutionastext_sm VARCHAR[],
b1g_dct_provenancestatement_sm VARCHAR[],
b1g_admintags_sm VARCHAR[]
```

### 3. API Integration

The field mapping is automatically applied in the `process_resource` function (`app/api/v1/utils.py`), ensuring all API responses use proper OGM field names.

## BTAA OGM Aardvark Schema

The implementation follows the BTAA OGM Aardvark schema with these required fields:

### Core Required Fields
- `id` - Resource identifier
- `gbl_mdVersion_s` - Metadata version (must be "Aardvark")
- `schema_provider_s` - Schema provider
- `dct_title_s` - Resource title
- `dct_description_sm` - Resource description
- `dct_language_sm` - Resource language(s)
- `dct_accessRights_s` - Access rights
- `dct_license_sm` - License information

### BTAA Required Fields
- `b1g_code_s` - GeoBTAA custom code
- `b1g_dct_accrualMethod_s` - Accrual method
- `b1g_dateAccessioned_s` - Date accessioned
- `b1g_publication_state_s` - Publication state
- `b1g_language_sm` - BTAA language(s)

### Optional BTAA Fields
- `b1g_status_s` - Record status
- `b1g_dct_accrualPeriodicity_s` - Accrual periodicity
- `b1g_dateRetired_s` - Date retired
- `b1g_child_record_b` - Child record flag
- `b1g_dct_mediator_sm` - Mediator information
- `b1g_access_s` - Access control object
- `b1g_image_ss` - Image URL
- `b1g_geonames_sm` - GeoNames references
- `b1g_creatorID_sm` - Creator identifiers
- `b1g_dct_conformsTo_sm` - Conformance statements
- `b1g_dcat_spatialResolutionInMeters_sm` - Spatial resolution
- `b1g_geodcat_spatialResolutionAsText_sm` - Spatial resolution text
- `b1g_dct_provenanceStatement_sm` - Provenance statements
- `b1g_adminTags_sm` - Administrative tags

## Field Mapping Examples

| Database Field | OGM Field | Description |
|----------------|-----------|-------------|
| `gbl_mdversion_s` | `gbl_mdVersion_s` | Metadata version |
| `gbl_resourceclass_sm` | `gbl_resourceClass_sm` | Resource class |
| `gbl_resourcetype_sm` | `gbl_resourceType_sm` | Resource type |
| `dct_accessrights_s` | `dct_accessRights_s` | Access rights |
| `b1g_dct_accrualmethod_s` | `b1g_dct_accrualMethod_s` | Accrual method |
| `b1g_dateaccessioned_s` | `b1g_dateAccessioned_s` | Date accessioned |

## Usage

### 1. Running the Migration

To add BTAA fields to your database:

```bash
python run_btaa_migration.py
```

### 2. Using the Field Mapper

```python
from app.services.ogm_field_mapper import OGMFieldMapper

# Map database fields to OGM fields
db_resource = {"gbl_resourceclass_sm": ["Datasets"]}
ogm_resource = OGMFieldMapper.map_resource_fields(db_resource)
# Result: {"gbl_resourceClass_sm": ["Datasets"]}

# Get required fields
required = OGMFieldMapper.get_required_fields()

# Get all schema fields
all_fields = OGMFieldMapper.get_all_schema_fields()
```

### 3. Example API Response

After processing, API responses will contain properly formatted OGM field names:

```json
{
  "data": {
    "type": "resources",
    "id": "02236876-9c21-42f6-9870-d2562da8e44f",
    "attributes": {
      "gbl_mdVersion_s": "Aardvark",
      "gbl_resourceClass_sm": ["Datasets", "Web services"],
      "b1g_code_s": "UMN-METRO-001",
      "b1g_status_s": "active",
      "b1g_dateAccessioned_s": "2021-06-01"
    }
  }
}
```

## Testing

Run the test suite to verify field mapping functionality:

```bash
pytest tests/test_ogm_field_mapper.py -v
```

## Example Scripts

### BTAA Processing Example

```bash
python examples/btaa_ogm_example.py
```

This demonstrates:
- Database field mapping
- BTAA field validation
- Required field checking
- Complete record processing

## Migration Notes

### Database Changes
- New BTAA fields added to `resources` table
- Fields use appropriate PostgreSQL types (VARCHAR, DATE, BOOLEAN, ARRAY, JSONB)
- Existing data remains unchanged

### Elasticsearch Changes
- New BTAA fields added to index mapping
- Fields indexed as appropriate types (keyword, date, boolean, object)
- Existing indices may need reindexing

### API Changes
- Field mapping applied automatically
- No breaking changes to existing endpoints
- Enhanced validation for BTAA compliance

## Compliance

The implementation ensures:

1. **Schema Compliance**: All required BTAA OGM Aardvark fields are supported
2. **Field Naming**: Proper OGM field names in API responses
3. **Data Types**: Correct PostgreSQL and Elasticsearch data types
4. **Validation**: Required field validation and reporting
5. **Backward Compatibility**: Existing functionality preserved

## Future Enhancements

Potential improvements:

1. **Schema Validation**: JSON Schema validation for BTAA records
2. **Field Constraints**: Enumerated value constraints for status fields
3. **Geographic Validation**: Coordinate system and geometry validation
4. **Quality Metrics**: Data quality scoring for BTAA compliance
5. **Export Formats**: BTAA-specific export formats (CSV, XML)

## Support

For questions or issues with BTAA OGM Aardvark implementation:

1. Check the test suite for examples
2. Review the field mapping configuration
3. Verify database schema matches expectations
4. Check Elasticsearch mapping compatibility
5. Review API response formatting

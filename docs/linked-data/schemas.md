# Schemas

{% include-markdown "includes/wip.md" %}

JSON Schemas provide structural validation for linked data, ensuring data quality and consistency across the BTAA Geospatial ecosystem.

## Overview

Schemas in this repository define:

- **Data structure**: Required and optional fields
- **Data types**: String, number, object, array constraints
- **Value constraints**: Enumerations, ranges, patterns
- **Relationships**: References between different data types
- **Validation rules**: Business logic and constraints

## Available Schemas

### OGM Aardvark Resource Record for BTAA Geospatial

**File**: [`schemas/ogm-aardvark-btaa.schema.json`](../schemas/ogm-aardvark-btaa.schema.json)

Validates OpenGeoMetadata Aardvark schema fields with BTAA custom elements for geospatial resource records.

**Key Features**:

- OpenGeoMetadata Aardvark compliance
- BTAA B1G custom extensions
- Dublin Core metadata validation
- Spatial and temporal coverage validation
- Access rights and licensing validation
- Provenance and administrative metadata

**Required Fields**:

- `id` - Resource identifier
- `gbl_mdVersion_s` - Metadata version (must be "Aardvark")
- `schema_provider_s` - Schema provider
- `dct_title_s` - Resource title
- `dct_description_sm` - Resource descriptions
- `dct_language_sm` - Languages
- `dct_accessRights_s` - Access rights ("Public" or "Restricted")
- `dct_license_sm` - License URIs
- `b1g_dct_accrualMethod_s` - Accrual method
- `b1g_dateAccessioned_s` - Accession date
- `b1g_publication_state_s` - Publication state


**Core Aardvark Properties**:

- **Identifiers**: `id`, `gbl_mdVersion_s`, `schema_provider_s`
- **Titles & Descriptions**: `dct_title_s`, `dct_alternative_sm`, `dct_description_sm`
- **Agents**: `dct_creator_sm`, `dct_publisher_sm`, `dct_rightsHolder_sm`
- **Subjects & Keywords**: `dct_subject_sm`
- **Languages**: `dct_language_sm`
- **Rights & Access**: `dct_accessRights_s`, `dct_license_sm`
- **Resource Classification**: `gbl_resourceClass_sm`, `gbl_resourceType_sm`
- **Temporal Coverage**: `dct_temporal_sm`, `dct_issued_s`
- **Spatial Coverage**: `dct_spatial_sm`, `dcat_bbox`, `dcat_centroid`, `locn_geometry`
- **Relationships**: `dct_source_sm`, `dct_isPartOf_sm`, `pcdm_memberOf_sm`, `dct_replaces_sm`, `dct_isReplacedBy_sm`, `dct_isVersionOf_sm`, `dct_relation_sm`
- **Technical**: `layer_geom_type_s`, `solr_year_i`, `layer_id_s`, `suppressed_b`, `dct_references_s`

**BTAA Custom Properties**:

- **Institutional**: `b1g_code_s`, `b1g_status_s`, `b1g_publication_state_s`
- **Dates**: `b1g_dateAccessioned_s`, `b1g_dateRetired_s`
- **Accrual**: `b1g_dct_accrualMethod_s`, `b1g_dct_accrualPeriodicity_s`
- **Access Control**: `b1g_access_s` (object with URI values), `b1g_child_record_b`
- **Geographic**: `b1g_geonames_sm` (URI array), `b1g_dcat_spatialResolutionInMeters_sm`, `b1g_geodcat_spatialResolutionAsText_sm`
- **Administrative**: `b1g_adminTags_sm`, `b1g_dct_provenanceStatement_sm`
- **UI**: `b1g_image_ss` (URI), `b1g_language_sm`, `b1g_creatorID_sm` (URI array), `b1g_dct_conformsTo_sm` (URI array)

**Data Type Constraints**:

- **Enums**: `gbl_mdVersion_s` must be "Aardvark", `dct_accessRights_s` must be "Public" or "Restricted"
- **Formats**: `gbl_mdModified_dt` (date-time), `b1g_dateAccessioned_s` (date), `b1g_dateRetired_s` (date)
- **URIs**: `dct_license_sm`, `b1g_image_ss`, `b1g_geonames_sm`, `b1g_creatorID_sm`, `b1g_dct_conformsTo_sm`
- **Arrays**: Most multi-valued properties are arrays of strings
- **Objects**: `b1g_access_s` allows additional properties with URI values
- **Booleans**: `suppressed_b`, `b1g_child_record_b`

**Example Usage**:

```json
{
  "id": "msn-id-1897",
  "gbl_mdVersion_s": "Aardvark",
  "schema_provider_s": "University of Wisconsin-Madison",
  "dct_title_s": "Wisconsin Population Density 2020",
  "dct_description_sm": ["Population density data for Wisconsin counties"],
  "dct_language_sm": ["en"],
  "dct_accessRights_s": "Public",
  "dct_license_sm": ["https://creativecommons.org/licenses/by/4.0/"],
  "b1g_code_s": "WISC",
  "b1g_dct_accrualMethod_s": "periodic",
  "b1g_dateAccessioned_s": "2024-01-15",
  "b1g_publication_state_s": "published",
  "b1g_language_sm": ["English"],
  "dct_spatial_sm": ["Wisconsin"],
  "dcat_bbox": "POLYGON((-92.9 42.5, -86.8 42.5, -86.8 47.1, -92.9 47.1, -92.9 42.5))",
  "dcat_centroid": "-89.85,44.8",
  "gbl_resourceClass_sm": ["Datasets"],
  "dct_creator_sm": ["US Census Bureau"],
  "b1g_geonames_sm": ["http://sws.geonames.org/5279468/"],
  "b1g_image_ss": "https://example.org/thumbnail.jpg"
}
```

## Validation

### Command Line Validation

```bash
# Validate schema files themselves
python scripts/validate_schema.py --validate-schemas

# Validate data against a specific schema
python scripts/validate_schema.py --schema schemas/ogm-aardvark-btaa.schema.json --data data/example.json

# Using jsonschema CLI
pip install jsonschema
jsonschema -i data/resource.json schemas/ogm-aardvark-btaa.schema.json
```

### Programmatic Validation

```python
import json
from jsonschema import validate, ValidationError

def validate_resource(data):
    """Validate resource against OGM Aardvark BTAA schema."""
    with open('schemas/ogm-aardvark-btaa.schema.json') as f:
        schema = json.load(f)
    
    try:
        validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        return False, e.message

# Usage
data = {
    "id": "example-resource-001",
    "gbl_mdVersion_s": "Aardvark",
    "schema_provider_s": "BTAA Geospatial Information Network",
    "dct_title_s": "Test Dataset",
    "dct_description_sm": ["A test dataset"],
    "dct_language_sm": ["en"],
    "dct_accessRights_s": "Public",
    "dct_license_sm": ["https://creativecommons.org/licenses/by/4.0/"],
    "b1g_code_s": "TEST",
    "b1g_dct_accrualMethod_s": "manual",
    "b1g_dateAccessioned_s": "2024-01-15",
    "b1g_publication_state_s": "published",
    "b1g_language_sm": ["en"]
}

is_valid, error = validate_resource(data)
if is_valid:
    print("✓ Resource is valid")
else:
    print(f"✗ Validation error: {error}")
```

### Integration with JSON-LD Contexts

Schemas work alongside JSON-LD contexts to provide both structural validation and semantic meaning:

```json
{
  "$schema": "https://gin.btaa.org/ld/schemas/ogm-aardvark-btaa.schema.json",
  "@context": "https://gin.btaa.org/ld/contexts/ogm-aardvark-btaa.context.jsonld",
  "@type": "Dataset",
  "id": "validated-resource",
  "dct_title_s": "Validated Dataset",
  "dct_description_sm": ["This dataset passes both schema and context validation"]
}
```

## Schema Registry

All schemas are registered with canonical URIs:

- `https://gin.btaa.org/ld/schemas/ogm-aardvark-btaa.schema.json`

These URIs can be referenced in `$schema` fields for IDE support and validation tools.

## Validation Tools

The repository includes several validation tools:

- **`validate_schema.py`** - Validate data against schemas
- **`validate_context.py`** - Validate JSON-LD contexts
- **`validate_vocabulary.py`** - Validate controlled vocabularies

These tools can be used individually or as part of CI/CD pipelines to ensure data quality.

## Schema Evolution

Schemas are versioned and may evolve over time:

- **Backward compatibility** is maintained when possible
- **New versions** are clearly documented
- **Migration guides** are provided for breaking changes
- **Deprecation notices** are given for removed features

## Related Documentation

- [Contexts](contexts.md) - JSON-LD context definitions
- [Profiles](profiles.md) - Profile specifications and constraints
- [Schemas](schemas.md) - JSON Schema validation
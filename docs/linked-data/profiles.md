# Profiles

{% include-markdown "includes/wip.md" %}

JSON-LD profiles define specific subsets of vocabularies and constraints for particular use cases, enabling targeted data exchange and validation within the BTAA Geospatial ecosystem.

## Overview

Profiles in this repository define:

- **Vocabulary subsets**: Curated sets of terms from broader vocabularies
- **Use case constraints**: Specific requirements for different data exchange scenarios
- **Validation rules**: Profile-specific validation and business logic
- **Interoperability guarantees**: Assurances about data compatibility
- **Implementation guidance**: Best practices for profile adoption

## What are JSON-LD Profiles?

JSON-LD profiles are specifications that define how to use JSON-LD in a particular context or for a specific purpose. They provide:

- **Constrained vocabularies**: Only specific terms from broader vocabularies
- **Mandatory properties**: Required fields for profile compliance
- **Value constraints**: Allowed values and formats
- **Extension points**: Where and how to add custom properties
- **Implementation guidance**: How to use the profile effectively

## Available Profiles

### OGM Aardvark Profile (BTAA-enhanced)

**Purpose**: Comprehensive geospatial resource description using the OpenGeoMetadata Aardvark schema with BTAA-specific extensions

**File**: [`https://gin.btaa.org/api/v1/ld/profiles/ogm-b1g.profile.jsonld`](https://gin.btaa.org/api/v1/ld/profiles/ogm-b1g.profile.jsonld)

**Scope**: JSON:API Resource attributes for maps, datasets, imagery, and collections in the BTAA network

**Key Features**:
- OpenGeoMetadata Aardvark schema compliance
- BTAA-specific custom elements and constraints
- JSON:API Resource attribute structure
- Comprehensive validation rules
- Integration with BTAA GIN infrastructure

**Required Properties**:

- `id` - Resource identifier
- `dct_title_s` - Resource title
- `gbl_resourceClass_sm` - Resource classification
- `dct_accessRights_s` - Access rights information
- `gbl_mdVersion_s` - Metadata version
- `b1g_dct_accrualMethod_s` - Accrual method
- `b1g_dateAccessioned_s` - Date accessioned
- `b1g_publication_state_s` - Publication state

**Recommended Properties**:

- `dct_description_sm` - Resource description
- `dct_language_sm` - Resource language
- `dct_subject_sm` - Subject terms
- `dcat_keyword_sm` - Keywords
- `schema_provider_s` - Provider information
- `dct_spatial_sm` - Spatial coverage
- `dct_references_s` - Reference links
- `dct_format_s` - Format information
- `dcat_bbox` - Bounding box
- `locn_geometry` - Geometry (WKT)
- `b1g_dct_conformsTo_sm` - Conformance statements
- `b1g_geonames_sm` - GeoNames URIs
- `b1g_image_ss` - Image URLs
- `b1g_dct_accrualPeriodicity_s` - Accrual periodicity
- `b1g_dcat_spatialResolutionInMeters_sm` - Spatial resolution
- `b1g_dct_provenanceStatement_sm` - Provenance information

**Temporal Coverage Constraints**:

The profile requires at least one of the following temporal properties:

- `dct_temporal_sm` - Temporal coverage
- `gbl_indexYear_im` - Index year
- `gbl_dateRange_drsim` - Date range

**Cardinality Rules**:

- Single values: `id`, `dct_title_s`, `dct_accessRights_s`, `gbl_mdVersion_s`, `b1g_dct_accrualMethod_s`, `b1g_dateAccessioned_s`, `b1g_publication_state_s`
- Multi-values: `gbl_resourceClass_sm`, `b1g_language_sm`

**Pattern Constraints**:

- `dcat_centroid`: Must match pattern `^-?\d+(\.\d+)?,\s*-?\d+(\.\d+)?$` (latitude,longitude)

**JSON Stringified Properties**:

- `dct_references_s` - Reference links as JSON string
- `b1g_access_s` - Access map as JSON string

**Example Usage**:

```json
{
  "@context": "https://gin.btaa.org/api/v1/ld/profiles/ogm-b1g.profile.jsonld",
  "@type": "Dataset",
  "id": "msn-id-1897",
  "dct_title_s": "Wisconsin Population Density 2020",
  "dct_description_sm": ["Population density data for Wisconsin counties"],
  "gbl_resourceClass_sm": ["Datasets"],
  "dct_accessRights_s": "Public",
  "gbl_mdVersion_s": "Aardvark",
  "b1g_dct_accrualMethod_s": "periodic",
  "b1g_dateAccessioned_s": "2024-01-15",
  "b1g_publication_state_s": "published",
  "b1g_language_sm": ["English"],
  "dct_spatial_sm": ["Wisconsin"],
  "dcat_bbox": "POLYGON((-92.9 42.5, -86.8 42.5, -86.8 47.1, -92.9 47.1, -92.9 42.5))",
  "b1g_code_s": "WISC"
}
```

### OGM UI Hints Profile

**Purpose**: Non-RDF UI overlay for BTAA resources carried in JSON:API Resource meta

**File**: [`https://gin.btaa.org/api/v1/ld/profiles/ogm-ui.profile.jsonld`](https://gin.btaa.org/api/v1/ld/profiles/ogm-ui.profile.jsonld)

**Scope**: UI-specific metadata for viewer integration and citation display

**Key Features**:

- UI component specifications
- Viewer protocol definitions
- Citation formatting hints
- Non-RDF structure for UI integration

**Recommended Properties**:

- `ui.citation` - Citation display information
- `ui.viewer.protocol` - Viewer protocol type
- `ui.viewer.endpoint` - Viewer endpoint URL

**Cardinality Rules**:

- `ui`: 0..1 (optional)
- `ui.citation`: 0..1 (optional)
- `ui.viewer`: 0..1 (optional)
- `ui.viewer.protocol`: 0..1 (optional)
- `ui.viewer.endpoint`: 0..1 (optional)
- `ui.viewer.geometry`: 0..1 (optional)

**Protocol Enums**:

The `ui.viewer.protocol` property supports these values:

- `iiif_manifest` - IIIF Manifest
- `tilejson` - TileJSON
- `wms` - Web Map Service
- `wmts` - Web Map Tile Service
- `xyz` - XYZ Tiles
- `arcgis` - ArcGIS Services

**Example Usage**:

```json
{
  "@context": "https://gin.btaa.org/ld/contexts/ogm-ui.context.jsonld",
  "ui": {
    "citation": "Wisconsin Population Density 2020. University of Wisconsin-Madison.",
    "viewer": {
      "protocol": "wms",
      "endpoint": "https://geoserver.example.org/geoserver/wms",
      "geometry": "{\"type\":\"Polygon\",\"coordinates\":[[[-92.9,42.5],[-86.8,42.5],[-86.8,47.1],[-92.9,47.1],[-92.9,42.5]]]}"
    }
  }
}
```

## Profile Validation

### Profile Compliance

Each profile defines specific validation rules that data must satisfy:

```python
import json
from jsonschema import validate

def validate_profile(data, profile_name):
    """Validate data against a specific profile."""
    profile_schema = load_profile_schema(profile_name)
    
    try:
        validate(instance=data, schema=profile_schema)
        return True, "Profile validation passed"
    except ValidationError as e:
        return False, f"Profile validation failed: {e.message}"
```

### Profile Selection

Choose the appropriate profile based on your use case:

- **OGM Aardvark Profile**: Comprehensive geospatial metadata with BTAA extensions
- **OGM UI Hints Profile**: UI integration and viewer specifications

## Implementation Guidelines

### Creating Profile-Compliant Data

1. **Select the appropriate profile** for your use case
2. **Include the required context** for the profile
3. **Provide all mandatory properties** as specified
4. **Follow value constraints** and format requirements
5. **Validate your data** against the profile schema

### Profile Extensions

Profiles can be extended with additional properties while maintaining compliance:

```json
{
  "@context": "https://gin.btaa.org/ld/contexts/ogm-aardvark-btaa.context.jsonld",
  "@type": "Dataset",
  "dct_title_s": "Example Dataset",
  // ... required profile properties ...
  
  // Profile extensions
  "custom:specialProperty": "Custom value",
  "custom:internalId": "INT-001"
}
```

### Best Practices

- **Use consistent identifiers** across your data
- **Provide meaningful descriptions** for all resources
- **Include appropriate spatial and temporal coverage**
- **Maintain provenance information** for data lineage
- **Regularly validate** against profile schemas
- **Document any extensions** to standard profiles
- **Follow JSON:API conventions** for resource structure

## Profile Evolution

Profiles are versioned and may evolve over time:

- **Backward compatibility** is maintained when possible
- **New versions** are clearly documented
- **Migration guides** are provided for breaking changes
- **Deprecation notices** are given for removed features

## Related Documentation

- [Contexts](contexts.md) - JSON-LD context definitions
- [Profiles](profiles.md) - Profile specifications and constraints
- [Schemas](schemas.md) - JSON Schema validation

# Contexts

{% include-markdown "includes/wip.md" %}

JSON-LD contexts provide mappings between terms used in JSON documents and IRIs. They are essential for creating interoperable linked data and ensuring consistent data interpretation across different systems.

## Overview

Contexts in this repository define:

- **Term mappings**: Short names for IRIs used in metadata records
- **Type coercions**: Automatic type conversion for dates, booleans, and other data types
- **Container specifications**: How arrays and sets should be handled
- **Namespace prefixes**: Short prefixes for common vocabularies and ontologies

## Available Contexts

### BTAA Aardvark Context

The primary context for GeoBTAA metadata records, extending the OpenGeoMetadata Aardvark schema with BTAA-specific elements.

**File**: [`https://gin.btaa.org/api/v1/ld/contexts/ogm-aardvark-btaa.context.jsonld`](https://gin.btaa.org/api/v1/ld/contexts/ogm-aardvark-btaa.context.jsonld)

This context provides mappings for:

#### Core Aardvark Elements
- **Identifiers**: `id_` → `dct:identifier`
- **Titles & Descriptions**: `dct_title_s`, `dct_alternative_sm`, `dct_description_sm`
- **Agents**: `dct_creator_sm`, `dct_publisher_sm`, `schema_provider_s`
- **Subjects & Keywords**: `dct_subject_sm`, `dcat_keyword_sm`
- **Languages**: `dct_language_sm`

#### Resource Classification
- **Resource Types**: `gbl_resourceClass_sm`, `gbl_resourceType_sm`
- **Formats & Themes**: `dct_format_s`, `dcat_theme_sm`

#### Temporal Coverage
- **Temporal**: `dct_temporal_sm`, `gbl_indexYear_im`, `gbl_dateRange_drsim`

#### Spatial Coverage
- **Spatial**: `dct_spatial_sm`
- **Geometry**: `locn_geometry` (WKT), `dcat_bbox`, `dcat_centroid`

#### Relationships
- **Part/Whole**: `dct_ispartof_sm`, `pcdm_memberOf_sm`
- **Versions**: `dct_isVersionOf_sm`, `dct_replaces_sm`, `dct_isReplacedBy_sm`
- **Sources**: `dct_source_sm`, `dct_relation_sm`

#### Rights & Access
- **Rights**: `dct_rights_sm`, `dct_license_sm`, `dct_rightsHolder_sm`
- **Access**: `dct_accessRights_s`

#### BTAA Custom Elements
- **Institutional**: `b1g_code_s`, `b1g_status_s`, `b1g_publication_state_s`
- **Dates**: `b1g_dateAccessioned_s`, `b1g_dateRetired_s`
- **Accrual**: `b1g_dct_accrualMethod_s`, `b1g_dct_accrualPeriodicity_s`
- **Access Control**: `b1g_access_s` (JSON map), `b1g_child_record_b`
- **Geographic**: `b1g_geonames_sm` (URIs), `b1g_dcat_spatialResolutionInMeters_sm`
- **Administrative**: `b1g_adminTags_sm`, `b1g_dct_provenanceStatement_sm`

### OGM UI Context

A specialized context for OpenGeoMetadata UI components and viewer integrations.

**File**: [`https://gin.btaa.org/api/v1/ld/contexts/ogm-ui.context.jsonld`](https://gin.btaa.org/api/v1/ld/contexts/ogm-ui.context.jsonld)

This context provides mappings for:

- **UI Components**: `ui`, `citation`, `viewer`
- **Protocols**: `protocol`
- **Endpoints**: `endpoint` (typed as IRI)
- **Geometry**: `geometry` (typed as JSON)

## Usage

### Including Contexts in Metadata Records

```json
{
  "@context": "https://gin.btaa.org/api/v1/ld/contexts/ogm-aardvark-btaa.context.jsonld",
  "@type": "Dataset",
  "dct_title_s": "Example Geospatial Dataset",
  "dct_creator_sm": ["University of Example"],
  "dct_spatial_sm": ["United States"],
  "b1g_code_s": "EXAMPLE"
}
```

### Using Multiple Contexts

```json
{
  "@context": [
    "https://gin.btaa.org/api/v1/ld/contexts/ogm-aardvark-btaa.context.jsonld",
    "https://gin.btaa.org/api/v1/ld/contexts/ogm-ui.context.jsonld"
  ],
  "@type": "Dataset",
  "dct_title_s": "Example Dataset",
  "viewer": {
    "protocol": "wms",
    "endpoint": "https://example.org/geoserver/wms"
  }
}
```

## Namespace Prefixes

The contexts include mappings for these common vocabularies:

- **dct**: Dublin Core Terms (`http://purl.org/dc/terms/`)
- **dcat**: Data Catalog Vocabulary (`http://www.w3.org/ns/dcat#`)
- **schema**: Schema.org (`https://schema.org/`)
- **gsp**: GeoSPARQL (`http://www.opengis.net/ont/geosparql#`)
- **gbl**: GeoBlacklight (`https://geo.blacklight.org/terms#`)
- **b1g**: BTAA GIN (`https://gin.btaa.org/terms/b1g#`)
- **ogm**: OpenGeoMetadata (`https://opengeometadata.org/ogm/terms#`)

## Type Coercions

The contexts automatically handle type conversions:

- **Dates**: `xsd:date` for accessioned/retired dates
- **DateTimes**: `xsd:dateTime` for modification timestamps
- **Booleans**: `xsd:boolean` for flags like `georeferenced`, `suppressed`
- **Decimals**: `xsd:decimal` for spatial resolution values
- **JSON**: `@json` for complex objects like references and access maps
- **IRIs**: `@id` for URIs and identifiers

## Container Specifications

- **Sets**: `@container: @set` for multi-valued properties
- **Arrays**: Standard JSON arrays for ordered collections
- **Language Maps**: Automatic language tagging for internationalized content

## Related Documentation

- [Contexts](contexts.md) - JSON-LD context definitions
- [Profiles](profiles.md) - Profile specifications and constraints
- [Schemas](schemas.md) - JSON Schema validation

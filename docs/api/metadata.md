# Metadata

{% include-markdown "includes/wip.md" %}

## OGM Aardvark

[OGM Aardvark](https://opengeometadata.org/ogm-aardvark/) ([https://opengeometadata.org/ogm-aardvark](https://opengeometadata.org/ogm-aardvark)) is a lightweight metadata profile for geospatial discovery. Every resource is a single JSON object that **MUST** include the following required properties:

| Field | Type | Description |
| :---- | :---- | :---- |
| `id` | string | Stable identifier (slug or UUID). |
| `dct_title_s` | string | Human‑readable title. |
| `dct_accessRights_s` | string | Only one of two values are allowed: Public or Restricted. |
| `gbl_resourceClass_sm` | array of strings | Provides a top level set of categories for classifying the resource. |
| `gbl_mdModified_dt` | string (date‑time) | Last modified timestamp. |
| `gbl_mdVersion_s` | string | MUST be `Aardvark`. |
| [Full OGM Aardvark Schema Definition](https://opengeometadata.org/ogm-aardvark/) |  |  |

## BTAA Geospatial Metadata Profile 

Every resource **MUST** include the following required BTAA properties:

| Field | Type | Description |
| :---- | :---- | :---- |
| `b1g_dct_accrualMethod_s` | string | To describe how the record was obtained. |
| `b1g_dateAccessioned_s` | string | To store the date a record was harvested. |
| `b1g_publication_state_s` | string | To communicate if the resource is public or hidden. |
| [Full BTAA Extension Schema Definition](https://gin.btaa.org/metadata/b1g-custom-elements/) |  |  |

## OGM+BTAA Geospatial

Combined OGM+BTAA Geospatial required attributes:

| Field | Type | Description |
| :---- | :---- | :---- |
| `id` | string | Stable identifier (slug or UUID). |
| `dct_title_s` | string | Human‑readable title. |
| `dct_accessRights_s` | string | Only one of two values are allowed: Public or Restricted. |
| `gbl_resourceClass_sm` | array of strings | Provides a top level set of categories for classifying the resource. |
| `gbl_mdModified_dt` | string (date‑time) | Last modified timestamp. |
| `gbl_mdVersion_s` | string | MUST be `Aardvark`. |
| `b1g_dct_accrualMethod_s` | string | To describe how the record was obtained. |
| `b1g_dateAccessioned_s` | string | To store the date a record was harvested. |
| `b1g_publication_state_s` | string | To communicate if the resource is public or hidden. |

The obligation for all other fields defined in the canonical Aardvark schema is **MAY**.

## JSON Schema

JSON Schema file for OGM resources is maintained at: [https://opengeometadata.org/schema/geoblacklight-schema-aardvark.json](https://opengeometadata.org/schema/geoblacklight-schema-aardvark.json)


## JSON-LD Context

JSON-LD context for OGM+BTAA Aardvark records: [DRAFT PR](https://raw.githubusercontent.com/OpenGeoMetadata/opengeometadata.github.io/18896025536dae80b632aa5b059fb001d3d42c56/docs/context/aardvark.json)

## CSV

OGM+BTAA Geospatial also has a tabular CSV expression with an [Open Knowledge Foundation](https://okfn.org/en/) \> [Frictionless Data](https://frictionlessdata.io/) \> [Table Schema](https://datapackage.org/standard/table-schema/) schema definition. Unlike OGM+BTAA Geospatial Aardvark JSON, OGM+BTAA Geospatial Aardvark CSV is comprised of two files:

1. Primary — The primary Aardvark metadata elements (primary.csv)  
2. Distributions — The dct\_reference\_s elements (distributions.csv)

## Table Schema

### CSV File Examples

These example CSV files use the GeoBlacklight fixture set.

* Primary — [gbl\_fixtures\_primary.csv](https://github.com/OpenGeoMetadata/opengeometadata.github.io/blob/api/docs/schema/gbl_fixtures_primary.csv)  
* Distributions — [gbl\_fixtures\_distributions.csv](https://github.com/OpenGeoMetadata/opengeometadata.github.io/blob/api/docs/schema/gbl_fixtures_distributions.csv)

### Table Schema Files


These files can be used to validate the CSV examples against our CSV schema.

* Primary — [ogm\_aardvark\_primary.schema.json](https://github.com/OpenGeoMetadata/opengeometadata.github.io/blob/api/docs/schema/ogm_aardvark_primary.schema.json)  
* Distributions — [ogm\_aardvark\_distributions.schema.json](https://github.com/OpenGeoMetadata/opengeometadata.github.io/blob/api/docs/schema/ogm_aardvark_distributions.schema.json)

## TODOs

* JSON Schema for OGM+BTAA Geospatial
* JSON-LD Contexts
* Create BTAA CSV examples
* Create BTAA schema files  
# BTAA Geospatial Linked Data

{% include-markdown "includes/wip.md" %}

## Overview

The Linked Data section of this site describes our linked data assets:

- **JSON-LD Contexts**: Dictionaries that tell computers what each field in your JSON means by pointing to shared web definitions.
- **JSON-LD Profiles**: Rulebooks for that says which fields you should include and how to use them.
- **JSON Schemas**: Checklists for validating your JSON—what fields are allowed, their types, and which ones are required.

## Why Linked Data?

These files are the "glue" that makes our BTAA Geospatial API data dependable and reusable across tools and campuses. 

**Contexts** give shared meaning to each field so QGIS, web apps, and aggregators all "speak the same language". When you see `dct_title_s` in our API response, the context tells you it means "Dublin Core title" and points to the official definition.

**Profiles** set the rules for what a valid record must include, so results are consistent and interoperable. They ensure that every geospatial resource has the essential metadata needed for discovery and use.

**JSON Schemas** enforce those rules automatically, catching mistakes early and keeping the API trustworthy. They validate that required fields are present, data types are correct, and values meet our standards.

## The Big Picture

Together, these linked data assets enable:

- **Clean harvesting**: Aggregators can confidently pull data knowing it follows consistent patterns
- **Easier integrations**: Developers can build tools that work with our API without guessing what fields mean
- **Better search**: Search engines understand the semantic meaning of our metadata
- **Long-term stability**: Versioned schemas and contexts ensure data remains usable as technology evolves

## Our Approach

We plan to be very good stewards of this data. This means:

- **Standards-based**: Building on established vocabularies like OpenGeoMetadata and Schema.org
- **Well-documented**: Clear explanations of what each field means and how to use it
- **Versioned**: Careful management of changes to maintain backward compatibility
- **Community-driven**: Working with the broader geospatial and library communities

## Available Assets

### [Contexts](contexts.md)
JSON-LD context files that define the vocabulary and structure of our metadata:
- **OGM Aardvark Context**: Core OpenGeoMetadata Aardvark schema with BTAA extensions
- **OGM UI Context**: UI-specific terms for viewer integration and citation display

### [Profiles](profiles.md)
Rulebooks that define how to use our vocabularies for specific use cases:
- **OGM Aardvark Profile**: Comprehensive geospatial resource description with BTAA extensions
- **OGM UI Hints Profile**: UI integration and viewer specifications

### [Schemas](schemas.md)
JSON Schema validation files that enforce data quality:
- **OGM Aardvark Schema**: Structural validation for geospatial resource records

## Getting Started

1. **Start with Contexts**: Understand what each field in our API responses means
2. **Review Profiles**: Learn the rules for creating valid metadata records
3. **Use Schemas**: Validate your data to ensure it meets our standards
4. **Build Tools**: Create applications that leverage our structured, semantic data

## Standards and Best Practices

We adhere to established standards and best practices:

- [JSON-LD](https://json-ld.org/) for data serialization
- [OpenGeoMetadata](https://opengeometadata.org/) for geospatial metadata standards
- [JSON Schema](https://json-schema.org/) for validation

## Contact

For questions about our linked data assets or to contribute, please:
- [Open an issue](https://github.com/geobtaa/api/issues) on GitHub
- Contact the BTAA Geospatial Data Working Group
- Join our community discussions 
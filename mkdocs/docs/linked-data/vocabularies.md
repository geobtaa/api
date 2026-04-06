# Vocabularies

{% include-markdown "includes/wip.md" %}

Controlled vocabularies provide standardized terms and concepts for consistent data classification and discovery.

## Overview

Vocabularies in this repository include:

- **Subject classifications**: Topic and discipline terms
- **Geographic terms**: Place names and administrative boundaries
- **Temporal periods**: Historical and geological time periods
- **Resource types**: Dataset and collection classifications
- **Access levels**: Usage and licensing terms

## Available Vocabularies

### Subject Classification

Standard subject terms for geospatial data:

```json
{
  "@context": "https://schema.org/",
  "@type": "DefinedTermSet",
  "name": "BTAA Geospatial Subject Classification",
  "description": "Controlled vocabulary for geospatial data subjects",
  "hasDefinedTerm": [
    {
      "@type": "DefinedTerm",
      "termCode": "GEOGRAPHY",
      "name": "Geography",
      "description": "Study of places and relationships between people and environments"
    },
    {
      "@type": "DefinedTerm", 
      "termCode": "GEOLOGY",
      "name": "Geology",
      "description": "Study of Earth's physical structure and substance"
    }
  ]
}
```

### Geographic Terms

Hierarchical geographic classification:

```json
{
  "@context": "https://schema.org/",
  "@type": "DefinedTermSet",
  "name": "BTAA Geospatial Geographic Classification",
  "hasDefinedTerm": [
    {
      "@type": "DefinedTerm",
      "termCode": "MIDWEST",
      "name": "Midwest United States",
      "broaderTerm": "UNITED_STATES"
    }
  ]
}
```

## Usage

### Applying Vocabularies

```json
{
  "@context": "https://schema.org/",
  "@type": "Dataset",
  "name": "Midwest Population Data",
  "about": [
    {
      "@type": "DefinedTerm",
      "termCode": "GEOGRAPHY",
      "inDefinedTermSet": "https://raw.githubusercontent.com/geobtaa/ld/main/vocabularies/subjects.jsonld"
    },
    {
      "@type": "DefinedTerm", 
      "termCode": "MIDWEST",
      "inDefinedTermSet": "https://raw.githubusercontent.com/geobtaa/ld/main/vocabularies/geographic.jsonld"
    }
  ]
}
```

### Vocabulary Validation

Use the provided validation tools to ensure proper vocabulary usage:

```bash
# Validate vocabulary usage
python validate_vocabulary.py --input data.json --vocabulary subjects.jsonld
```

## Creating New Vocabularies

When creating new vocabularies:

1. **Research existing standards** first
2. **Define clear scope** and purpose
3. **Use consistent naming** conventions
4. **Provide definitions** for all terms
5. **Establish relationships** between terms
6. **Document versioning** strategy

## Best Practices

- **Reuse existing vocabularies** when possible (LCSH, AAT, etc.)
- **Use SKOS** for complex vocabulary structures
- **Provide multilingual support** where appropriate
- **Maintain backward compatibility** when possible
- **Document all changes** thoroughly 
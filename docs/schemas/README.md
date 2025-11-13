# JSON Schemas

This directory contains JSON Schema definitions for validating linked data structures in the BTAA Geospatial repository.

## Available Schemas

### BTAA Geospatial OGM Aardvark Resource Record (`resource.json`)

Validates OpenGeoMetadata Aardvark schema fields with BTAA Geospatial custom elements for geospatial resource records.

**Required fields:**

- `id` - Resource identifier
- `gbl_mdVersion_s` - Metadata version (must be "Aardvark")
- `schema_provider_s` - Schema provider
- `dct_title_s` - Resource title
- `dct_description_sm` - Resource descriptions
- `dct_language_sm` - Languages
- `dct_accessRights_s` - Access rights ("Public" or "Restricted")
- `b1g_dct_accrualMethod_s` - Accrual method
- `b1g_dateAccessioned_s` - Accession date
- `b1g_publication_state_s` - Publication state

**Key features:**

- OpenGeoMetadata Aardvark compliance
- BTAA Geospatial B1G custom extensions
- Dublin Core metadata validation
- Spatial and temporal coverage validation
- Access rights and licensing validation
- Provenance and administrative metadata

## Usage

### Validation with Python

```python
import json
from jsonschema import validate, ValidationError

# Load schema
with open('schemas/resource.json') as f:
    schema = json.load(f)

# Load data to validate
with open('data/resource.json') as f:
    data = json.load(f)

# Validate
try:
    validate(instance=data, schema=schema)
    print("✓ Data is valid")
except ValidationError as e:
    print(f"✗ Validation error: {e.message}")
```

### Validation with Command Line

```bash
# Using jsonschema CLI
pip install jsonschema
jsonschema -i data/resource.json schemas/resource.json

# Using our validation script
python scripts/validate_schema.py --schema schemas/resource.json --data data/resource.json
```

### Integration with JSON-LD

These schemas work alongside JSON-LD contexts to provide both structural validation and semantic meaning:

```json
{
  "id": "example-resource-001",
  "gbl_mdVersion_s": "Aardvark",
  "schema_provider_s": "BTAA Geospatial Information Network",
  "dct_title_s": "Midwest Population Density Data",
  "dct_description_sm": ["Population density data for the Midwest United States"],
  "dct_language_sm": ["en"],
  "dct_accessRights_s": "Public",
  "dct_license_sm": ["https://creativecommons.org/licenses/by/4.0/"],
  "b1g_code_s": "MIDWEST_POP_2020",
  "b1g_dct_accrualMethod_s": "manual",
  "b1g_dateAccessioned_s": "2024-01-15",
  "b1g_publication_state_s": "published",
  "b1g_language_sm": ["en"]
}
```

## Schema Development

### Creating New Schemas

1. **Follow JSON Schema Draft 7** standards
2. **Use descriptive `$id`** URIs
3. **Include comprehensive descriptions**
4. **Test with sample data**
5. **Document all constraints**

### Best Practices

- **Reuse existing schemas** when possible
- **Use consistent naming** conventions
- **Provide clear error messages**
- **Test edge cases** thoroughly
- **Version schemas** appropriately

### Validation Scripts

Use the provided validation scripts in the `scripts/` directory:

- `validate_schema.py` - Validate data against schemas
- `validate_context.py` - Validate JSON-LD contexts
- `validate_vocabulary.py` - Validate controlled vocabularies

## Schema Registry

All schemas are registered with their canonical URIs:

- `https://gin.btaa.org/ld/schemas/resource.json`

These URIs can be referenced in `$schema` fields for IDE support and validation. 
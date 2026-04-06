# API Reference

This document provides technical reference information for working with the BTAA Geospatial linked data assets.

## JSON-LD Contexts

### Core Context

**File**: `contexts/core.jsonld`

Standard context for basic linked data operations.

```json
{
  "@context": {
    "@vocab": "https://schema.org/",
    "dc": "http://purl.org/dc/terms/",
    "geo": "http://www.opengis.net/ont/geosparql#",
    "prov": "http://www.w3.org/ns/prov#",
    "geobtaa": "https://geobtaa.org/ontology#"
  }
}
```

### Geospatial Context

**File**: `contexts/geospatial.jsonld`

Specialized context for geospatial data.

```json
{
  "@context": {
    "@vocab": "https://schema.org/",
    "geo": "http://www.opengis.net/ont/geosparql#",
    "wgs84": "http://www.w3.org/2003/01/geo/wgs84_pos#",
    "geojson": "https://purl.org/geojson/vocab#",
    "geobtaa": "https://geobtaa.org/ontology#"
  }
}
```

## Vocabulary APIs

### Subject Classification

**File**: `vocabularies/subjects.jsonld`

```json
{
  "@context": "https://schema.org/",
  "@type": "DefinedTermSet",
  "@id": "https://geobtaa.org/vocabularies/subjects",
  "name": "BTAA Geospatial Subject Classification",
  "hasDefinedTerm": [
    {
      "@type": "DefinedTerm",
      "@id": "https://
      // .org/vocabularies/subjects/GEOGRAPHY",
      "termCode": "GEOGRAPHY",
      "name": "Geography"
    }
  ]
}
```

### Geographic Classification

**File**: `vocabularies/geographic.jsonld`

```json
{
  "@context": "https://schema.org/",
  "@type": "DefinedTermSet",
  "@id": "https://geobtaa.org/vocabularies/geographic",
  "name": "BTAA Geospatial Geographic Classification",
  "hasDefinedTerm": [
    {
      "@type": "DefinedTerm",
      "@id": "https://geobtaa.org/vocabularies/geographic/MIDWEST",
      "termCode": "MIDWEST",
      "name": "Midwest United States"
    }
  ]
}
```

## Ontology APIs

### Core Ontology

**File**: `ontologies/core.ttl`

**Namespace**: `https://geobtaa.org/ontology#`

**Classes**:
- `geobtaa:Dataset` - Geospatial dataset
- `geobtaa:Collection` - Dataset collection
- `geobtaa:Service` - Geospatial service

**Properties**:
- `geobtaa:spatialCoverage` - Geographic extent
- `geobtaa:temporalCoverage` - Time period
- `geobtaa:dataQuality` - Quality metrics

### Provenance Ontology

**File**: `ontologies/provenance.ttl`

**Namespace**: `https://geobtaa.org/ontology#`

**Classes**:
- `geobtaa:ProcessingStep` - Data processing activity
- `geobtaa:DataDerivation` - Data lineage

**Properties**:
- `geobtaa:derivedFrom` - Source dataset
- `geobtaa:processingMethod` - Processing technique

## Validation APIs

### Context Validation

```python
import json
from jsonschema import validate

def validate_context(context_file):
    """Validate JSON-LD context structure."""
    with open(context_file) as f:
        context = json.load(f)
    
    # Basic context validation
    assert "@context" in context
    return True
```

### Vocabulary Validation

```python
def validate_vocabulary(vocab_file):
    """Validate vocabulary structure."""
    with open(vocab_file) as f:
        vocab = json.load(f)
    
    # Vocabulary validation rules
    assert vocab["@type"] == "DefinedTermSet"
    assert "hasDefinedTerm" in vocab
    return True
```

### Ontology Validation

```python
import rdflib

def validate_ontology(ontology_file):
    """Validate ontology structure."""
    g = rdflib.Graph()
    g.parse(ontology_file, format="turtle")
    
    # Check for basic ontology elements
    classes = list(g.subjects(rdflib.RDF.type, rdflib.OWL.Class))
    properties = list(g.subjects(rdflib.RDF.type, rdflib.OWL.ObjectProperty))
    
    return len(classes) > 0
```

## HTTP APIs

### Content Negotiation

All resources support content negotiation:

```bash
# Get JSON-LD
curl -H "Accept: application/ld+json" \
     https://geobtaa.org/contexts/core

# Get Turtle
curl -H "Accept: text/turtle" \
     https://geobtaa.org/ontologies/core

# Get RDF/XML
curl -H "Accept: application/rdf+xml" \
     https://geobtaa.org/vocabularies/subjects
```

### SPARQL Endpoint

Query the ontologies via SPARQL:

```bash
curl -X POST \
     -H "Content-Type: application/sparql-query" \
     -d "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10" \
     https://geobtaa.org/sparql
```

## Error Codes

| Code | Description |
|------|-------------|
| 400  | Bad Request - Invalid syntax |
| 404  | Not Found - Resource doesn't exist |
| 406  | Not Acceptable - Unsupported format |
| 500  | Internal Server Error |

## Rate Limits

- **Anonymous**: 100 requests/hour
- **Authenticated**: 1000 requests/hour
- **API Key**: 10000 requests/hour 
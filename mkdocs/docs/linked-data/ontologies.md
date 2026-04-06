# Ontologies

{% include-markdown "includes/wip.md" %}

Ontologies define semantic models and relationships for geospatial data, enabling advanced reasoning and discovery capabilities.

## Overview

Ontologies in this repository provide:

- **Data models**: Conceptual frameworks for geospatial data
- **Relationship definitions**: Semantic connections between entities
- **Inference rules**: Logical reasoning capabilities
- **Domain expertise**: Specialized knowledge representation

## Available Ontologies

### Core Geospatial Ontology

Basic geospatial concepts and relationships:

```turtle
@prefix geo: <http://www.opengis.net/ont/geosparql#> .
@prefix schema: <https://schema.org/> .
@prefix geobtaa: <https://geobtaa.org/ontology#> .

# Dataset class
geobtaa:Dataset a owl:Class ;
    rdfs:subClassOf schema:Dataset ;
    rdfs:label "Geospatial Dataset"@en ;
    rdfs:comment "A dataset containing geospatial data"@en .

# Spatial relationship
geobtaa:spatialCoverage a owl:ObjectProperty ;
    rdfs:domain geobtaa:Dataset ;
    rdfs:range geo:Feature ;
    rdfs:label "Spatial Coverage"@en ;
    rdfs:comment "The geographic extent of a dataset"@en .
```

### Provenance Ontology

Data lineage and attribution:

```turtle
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix geobtaa: <https://geobtaa.org/ontology#> .

# Data derivation
geobtaa:derivedFrom a owl:ObjectProperty ;
    rdfs:subPropertyOf prov:wasDerivedFrom ;
    rdfs:domain geobtaa:Dataset ;
    rdfs:range geobtaa:Dataset ;
    rdfs:label "Derived From"@en .

# Processing step
geobtaa:ProcessingStep a owl:Class ;
    rdfs:subClassOf prov:Activity ;
    rdfs:label "Processing Step"@en .
```

## Usage

### Querying with SPARQL

```sparql
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geobtaa: <https://geobtaa.org/ontology#>
PREFIX schema: <https://schema.org/>

SELECT ?dataset ?coverage
WHERE {
  ?dataset a geobtaa:Dataset ;
           geobtaa:spatialCoverage ?coverage .
  ?coverage geo:hasGeometry ?geometry .
}
```

### Reasoning with OWL

The ontologies support automated reasoning:

```python
import rdflib
from rdflib import Graph, Namespace

# Load ontology
g = Graph()
g.parse("ontologies/core.ttl", format="turtle")

# Create reasoner
from rdflib.plugins.sparql import prepareQuery
query = prepareQuery("""
    SELECT ?dataset WHERE {
        ?dataset a geobtaa:Dataset .
    }
""")

# Execute query
results = g.query(query)
```

## Creating New Ontologies

When creating new ontologies:

1. **Define clear scope** and purpose
2. **Reuse existing ontologies** when possible
3. **Use standard modeling patterns**
4. **Provide comprehensive documentation**
5. **Test with sample data**
6. **Version appropriately**

## Best Practices

- **Follow OWL 2 DL** for maximum reasoning capabilities
- **Use descriptive URIs** for all resources
- **Provide labels and comments** in multiple languages
- **Document all axioms** thoroughly
- **Test with reasoners** before release
- **Maintain backward compatibility** when possible

## Validation

Use ontology validation tools:

```bash
# Validate ontology structure
python validate_ontology.py --input ontologies/core.ttl

# Check for reasoning consistency
python check_consistency.py --input ontologies/core.ttl
``` 
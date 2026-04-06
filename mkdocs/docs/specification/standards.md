# Standards, Terminology, Conventions

{% include-markdown "includes/wip.md" %}

## Standards

* [OpenAPI / Version v3.1.1](https://spec.openapis.org/oas/v3.1.1.html)  
* [JSON API / Version v1.1](https://jsonapi.org/format/1.1/)  
* [JSON-LD / Version v1.1](https://www.w3.org/TR/json-ld11/)  
* [Model Context Protocol (MCP) / Version 1.0](https://modelcontextprotocol.io/specification/2025-06-18)

## Terminology

* **Resource** – An individual OpenGeoMetadata Aardvark \+ BTAA Geospatial Metadata Profile JSON object, document, item, or record.  
* **Service Document** – The JSON description of server capabilities (`/v1/service`).  
* **Identifier** – The canonical URI‑safe string that uniquely identifies a record.  
* **Model Context Protocol (MCP)** – A protocol that enables API responses to declare behavioral context using `profile` URIs. These profiles point to machine-readable documents describing how to interpret or interact with the resource, especially useful for generic agents, AI tools, or validators.

## Conventions

* All date/time values **MUST** be RFC 3339 (ISO 8601\) strings.  
* All numeric coordinates **MUST** be WGS‑84 (EPSG 4326\) decimal degrees.



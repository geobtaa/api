# Model Context Protocol (MCP)

{% include-markdown "includes/wip.md" %}

The BTAA Geospatial API supports [Model Context Protocol (MCP)](https://modelcontextprotocol.io/specification/2025-06-18), a formal specification for declaring the processing and behavioral context of an API response. MCP enables generic clients, validators, and AI agents to understand how to interpret metadata records and response payloads in a consistent, machine-readable way.

## Usage

**```GET /api/v1/mcp```**

```
{
  "name": "btaa-geospatial-api",
  "version": "0.8.8",
  "description": "BTAA Geospatial API MCP Service",
  "protocol": "mcp",
  "transports": [
    "stdio",
    "websocket"
  ],
  "capabilities": {
    "tools": [
      "search_resources",
      "get_resource",
      "get_resource_metadata",
      "list_resources",
      "get_suggestions",
      "get_resource_viewer",
      "validate_aardvark_record"
    ]
  },
  "connections": {
    "stdio": {
      "type": "stdio",
      "command": "python3",
      "args": [
        "mcp/run_mcp_service.py"
      ]
    },
    "websocket": {
      "type": "websocket",
      "url": "/api/v1/mcp/ws"
    }
  },
  "documentation": {
    "tools": {
      "search_resources": "Search for geospatial resources using text queries, filters, and sorting options",
      "get_resource": "Get a single geospatial resource by ID with full metadata and UI enhancements",
      "get_resource_metadata": "Get the OGM Aardvark record for a resource by ID",
      "list_resources": "List all geospatial resources with pagination",
      "get_suggestions": "Get search suggestions for autocomplete",
      "get_resource_viewer": "Get an HTML page with the embedded OGM viewer for a specific resource",
      "validate_aardvark_record": "Validate a single Aardvark JSON record against schema requirements"
    }
  }
}
```

## Profile URIs

Each URI in the profile array MUST resolve to a valid MCP document, which includes:

* @context: MUST include the MCP context (https://modelcontextprotocol.io/context/v1.jsonld)  
* @type: SHOULD be ModelContextProfile  
* title, description, appliesTo: for human/machine interpretation  
* features: optional keys describing supported behaviors, fields, or UI expectations

## Example MCP Profile (abridged)

```json
{
  "@context": "https://modelcontextprotocol.io/context/v1.jsonld",
  "@type": "ModelContextProfile",
  "id": "https://opengeometadata.org/profile/mcp/search",
  "title": "OGM Search Results Profile",
  "description": "Describes the structure and interpretation of search results.",
  "appliesTo": "https://opengeometadata.org/api/v1/search",
  "features": {
    "search": {
      "supportsGeoFilters": true,
      "maxResults": 1000,
      "defaultSort": "relevance"
    },
    "ui": {
      "viewer": true,
      "facets": true,
      "pagination": true
    }
  }
}
```

## Benefits

* Allows automated agents to reason about what’s returned  
* Enables consistent UI rendering and schema interpretation  
* Provides potential future extensibility without API versioning


## TODOs

* BTAA Examples instead of OGM Examples

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict

import aiohttp
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    ServerCapabilities,
    TextContent,
    Tool,
    ToolsCapability,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.services.search_service import SearchService
from db.config import DATABASE_URL
from db.models import resources

logger = logging.getLogger(__name__)

MCP_SERVICE_NAME = "btaa-geospatial-api"
MCP_SERVICE_VERSION = "0.6.0"
MCP_SERVICE_DESCRIPTION = "BTAA Geospatial API MCP Service"

# Lazy initialization of database engine and session
_engine = None
_async_session = None


def get_async_session():
    """Get the async session factory, creating it if necessary."""
    global _engine, _async_session
    try:
        if _engine is None:
            _engine = create_async_engine(DATABASE_URL)
            _async_session = sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
        return _async_session
    except Exception as e:
        logger.error(f"Failed to create database session: {e}")
        raise


class OGMMCPService:
    """MCP service for GeoBTAA API endpoints."""

    def __init__(self):
        logger.info("Initializing GeoBTAA MCP Service")
        self.server = Server(MCP_SERVICE_NAME)
        self.tool_specs = self._build_tool_specs()
        self.tool_handlers = self._build_tool_handlers()
        self._register_tools()
        logger.info("GeoBTAA MCP Service initialized successfully")

    def _build_tool_specs(self) -> list[dict[str, Any]]:
        """Single source of truth for MCP tool metadata."""
        return [
            {
                "name": "search_resources",
                "description": (
                    "Search for geospatial resources using text queries, filters, "
                    "and sorting options"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query string"},
                        "page": {
                            "type": "integer",
                            "description": "Page number (default: 1)",
                            "default": 1,
                        },
                        "per_page": {
                            "type": "integer",
                            "description": "Resources per page (max 100, default: 10)",
                            "default": 10,
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort option",
                            "enum": [
                                "relevance",
                                "year_desc",
                                "year_asc",
                                "title_asc",
                                "title_desc",
                            ],
                        },
                    },
                },
            },
            {
                "name": "get_resource",
                "description": (
                    "Get a single geospatial resource by ID with full metadata and UI enhancements"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "description": "Resource ID"}},
                    "required": ["id"],
                },
            },
            {
                "name": "get_resource_metadata",
                "description": "Get the OGM Aardvark record for a resource by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "description": "Resource ID"}},
                    "required": ["id"],
                },
            },
            {
                "name": "list_resources",
                "description": "List geospatial resources with pagination",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer", "description": "Page number", "default": 1},
                        "per_page": {
                            "type": "integer",
                            "description": "Resources per page (max 100)",
                            "default": 10,
                        },
                    },
                },
            },
            {
                "name": "get_suggestions",
                "description": "Get search suggestions for autocomplete",
                "inputSchema": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Search query"}},
                    "required": ["query"],
                },
            },
            {
                "name": "get_resource_viewer",
                "description": "Get an HTML page with the embedded OGM viewer for a resource",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Resource ID"},
                        "embed": {
                            "type": "boolean",
                            "description": "Embedded mode for iframe usage",
                            "default": False,
                        },
                    },
                    "required": ["id"],
                },
            },
            {
                "name": "get_resource_thumbnail",
                "description": (
                    "Get thumbnail endpoint result metadata (redirect, content type, URL)"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Resource ID"},
                        "no_cache": {
                            "type": "boolean",
                            "description": "Bypass cache and regenerate thumbnail",
                            "default": False,
                        },
                    },
                    "required": ["id"],
                },
            },
            {
                "name": "get_resource_distributions",
                "description": "Get structured resource distributions and protocol details",
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "description": "Resource ID"}},
                    "required": ["id"],
                },
            },
            {
                "name": "get_resource_links",
                "description": "Get all links associated with a resource",
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "description": "Resource ID"}},
                    "required": ["id"],
                },
            },
            {
                "name": "get_resource_downloads",
                "description": "Get resource download options",
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "description": "Resource ID"}},
                    "required": ["id"],
                },
            },
            {
                "name": "get_resource_citation",
                "description": "Get resource citation in default, JSON-LD, RIS, or BibTeX format",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Resource ID"},
                        "format": {
                            "type": "string",
                            "description": "Citation format",
                            "enum": ["default", "json-ld", "ris", "bibtex"],
                            "default": "default",
                        },
                    },
                    "required": ["id"],
                },
            },
            {
                "name": "get_search_facet_values",
                "description": (
                    "Get paginated facet values for a facet field in current search context"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "facet_name": {"type": "string", "description": "Facet field name"},
                        "q": {"type": "string", "description": "Search query"},
                        "page": {"type": "integer", "description": "Page number", "default": 1},
                        "per_page": {
                            "type": "integer",
                            "description": "Values per page",
                            "default": 10,
                        },
                        "sort": {
                            "type": "string",
                            "description": "Sort option",
                            "enum": ["count_desc", "count_asc", "alpha_asc", "alpha_desc"],
                            "default": "count_desc",
                        },
                        "q_facet": {"type": "string", "description": "Filter facet values by term"},
                        "adv_q": {"type": "string", "description": "Advanced query JSON string"},
                    },
                    "required": ["facet_name"],
                },
            },
            {
                "name": "get_resource_relationships",
                "description": "Get relationships for a resource",
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "description": "Resource ID"}},
                    "required": ["id"],
                },
            },
            {
                "name": "get_resource_similar_items",
                "description": "Get similar items for a resource",
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "description": "Resource ID"}},
                    "required": ["id"],
                },
            },
            {
                "name": "get_resource_static_map",
                "description": (
                    "Get static map endpoint result metadata (redirect/content type/URL)"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Resource ID"},
                        "no_cache": {
                            "type": "boolean",
                            "description": "Bypass cache and regenerate static map",
                            "default": False,
                        },
                    },
                    "required": ["id"],
                },
            },
            {
                "name": "get_ogm_repos",
                "description": "List OGM repositories exposed by the public API",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_ogm_harvest_failures",
                "description": "Get OGM harvest failures from the public API",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "validate_aardvark_record",
                "description": "Validate a single Aardvark JSON record against schema requirements",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "record": {
                            "type": "object",
                            "description": "Aardvark JSON record to validate",
                        }
                    },
                    "required": ["record"],
                },
            },
        ]

    def _build_tool_handlers(self) -> dict[str, Any]:
        return {
            "search_resources": self._search_resources,
            "get_resource": self._get_resource,
            "get_resource_metadata": self._get_resource_metadata,
            "list_resources": self._list_resources,
            "get_suggestions": self._get_suggestions,
            "get_resource_viewer": self._get_resource_viewer,
            "get_resource_thumbnail": self._get_resource_thumbnail,
            "get_resource_distributions": self._get_resource_distributions,
            "get_resource_links": self._get_resource_links,
            "get_resource_downloads": self._get_resource_downloads,
            "get_resource_citation": self._get_resource_citation,
            "get_search_facet_values": self._get_search_facet_values,
            "get_resource_relationships": self._get_resource_relationships,
            "get_resource_similar_items": self._get_resource_similar_items,
            "get_resource_static_map": self._get_resource_static_map,
            "get_ogm_repos": self._get_ogm_repos,
            "get_ogm_harvest_failures": self._get_ogm_harvest_failures,
            "validate_aardvark_record": self._validate_aardvark_record,
        }

    def _register_tools(self):
        """Register all API endpoints as MCP tools."""
        logger.info("Registering MCP tools")

        @self.server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            """List all available tools."""
            logger.debug("Handling list_tools request")
            return ListToolsResult(tools=[Tool(**spec) for spec in self.tool_specs])

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            """Handle tool calls."""
            logger.debug(f"Handling tool call: {name} with arguments: {arguments}")
            try:
                handler = self.tool_handlers.get(name)
                if not handler:
                    raise ValueError(f"Unknown tool: {name}")
                return await handler(arguments)
            except Exception as e:
                logger.error(f"Error in tool {name}: {str(e)}", exc_info=True)
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Error: {str(e)}")], isError=True
                )

        logger.info("MCP tools registered successfully")

    async def _search_resources(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Search for resources."""
        try:
            query = arguments.get("query")
            page = arguments.get("page", 1)
            per_page = arguments.get("per_page", 10)
            sort = arguments.get("sort")

            search_service = SearchService()
            results = await search_service.search(
                q=query,
                page=page,
                limit=per_page,
                sort=sort,
                request_query_params="",
                callback=None,
            )

            # Process each resource to get full details
            processed_resources = []
            async with get_async_session()() as session:
                for item in results.get("data", []):
                    try:
                        # Extract the resource data from the search result
                        resource_dict = item.get("attributes", {})
                        if not resource_dict:
                            continue

                        # Process the resource using the same logic as API endpoints
                        from app.api.v1.utils import process_resource

                        resource_object = await process_resource(resource_dict, session)
                        processed_resources.append(resource_object)
                    except Exception as e:
                        logger.error(f"Error processing search result: {str(e)}", exc_info=True)
                        continue

            # Return the full resource objects as JSON
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "query": query,
                                "total_results": len(results.get("data", [])),
                                "page": page,
                                "per_page": per_page,
                                "resources": processed_resources,
                            },
                            indent=2,
                        ),
                    )
                ]
            )
        except Exception as e:
            logger.error(f"Error in _search_resources: {e}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error searching resources: {str(e)}")],
                isError=True,
            )

    async def _get_resource(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Get a single resource."""
        try:
            # Validate arguments
            resource_id = arguments.get("id")
            if not resource_id:
                return CallToolResult(
                    content=[TextContent(type="text", text="Error: Missing 'id'")],
                    isError=True,
                )

            async with get_async_session()() as session:
                query = select(resources).where(resources.c.id == resource_id)
                result = await session.execute(query)
                row = result.fetchone()

                if not row:
                    return CallToolResult(
                        content=[
                            TextContent(type="text", text=f"Resource not found: {resource_id}")
                        ],
                        isError=True,
                    )

                # Convert to dict and sanitize datetime objects
                from app.api.v1.utils import sanitize_for_json

                resource_dict = sanitize_for_json(dict(row._mapping))

                # Process the resource using the same logic as API endpoints
                from app.api.v1.utils import process_resource

                resource_object = await process_resource(resource_dict, session)

                # Return the full resource object as JSON
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(resource_object, indent=2))]
                )
        except Exception as e:
            logger.error(f"Error in _get_resource: {e}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Database connection error: {str(e)}")],
                isError=True,
            )

    async def _get_resource_metadata(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Get Aardvark record for a resource."""
        try:
            # Validate arguments
            resource_id = arguments.get("id")
            if not resource_id:
                return CallToolResult(
                    content=[TextContent(type="text", text="Error: Missing 'id'")],
                    isError=True,
                )

            async with get_async_session()() as session:
                query = select(resources).where(resources.c.id == resource_id)
                result = await session.execute(query)
                row = result.fetchone()

                if not row:
                    return CallToolResult(
                        content=[
                            TextContent(type="text", text=f"Resource not found: {resource_id}")
                        ],
                        isError=True,
                    )

                # Convert to dict and sanitize datetime objects
                from app.api.v1.utils import sanitize_for_json

                resource_dict = sanitize_for_json(dict(row._mapping))

                # Map database column names to official Aardvark field names
                from app.services.ogm_field_mapper import OGMFieldMapper

                aardvark_attributes = OGMFieldMapper.map_resource_fields(resource_dict)

                # Filter out null values and empty arrays
                aardvark_record = {}
                for key, value in aardvark_attributes.items():
                    if value is not None and value != "":
                        # Handle empty arrays
                        if isinstance(value, list) and len(value) == 0:
                            continue
                        # Handle arrays with only None/empty values
                        if isinstance(value, list) and all(
                            item is None or item == "" for item in value
                        ):
                            continue
                        aardvark_record[key] = value

                # Return the cleaned Aardvark record as JSON
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(aardvark_record, indent=2))]
                )
        except Exception as e:
            logger.error(f"Error in _get_resource_metadata: {e}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Database connection error: {str(e)}")],
                isError=True,
            )

    async def _list_resources(self, arguments: Dict[str, Any]) -> CallToolResult:
        """List resources with pagination."""
        try:
            page = arguments.get("page", 1)
            per_page = arguments.get("per_page", 10)

            skip = (page - 1) * per_page
            limit = per_page

            async with get_async_session()() as session:
                query = select(resources).offset(skip).limit(limit)
                result = await session.execute(query)
                results = result.fetchall()

                # Get total count
                count_query = select(func.count(resources.c.id))
                count_result = await session.execute(count_query)
                total_count = count_result.scalar()

                # Process each resource to get full details
                processed_resources = []
                for row in results:
                    try:
                        # Convert to dict and sanitize datetime objects
                        from app.api.v1.utils import sanitize_for_json

                        resource_dict = sanitize_for_json(dict(row._mapping))

                        # Process the resource using the same logic as API endpoints
                        from app.api.v1.utils import process_resource

                        resource_object = await process_resource(resource_dict, session)
                        processed_resources.append(resource_object)
                    except Exception as e:
                        logger.error(f"Error processing resource: {str(e)}", exc_info=True)
                        continue

                # Return the full resource objects as JSON
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "page": page,
                                    "per_page": per_page,
                                    "total_count": total_count,
                                    "total_pages": (total_count + per_page - 1) // per_page,
                                    "resources": processed_resources,
                                },
                                indent=2,
                            ),
                        )
                    ]
                )
        except Exception as e:
            logger.error(f"Error in _list_resources: {e}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Database connection error: {str(e)}")],
                isError=True,
            )

    async def _get_suggestions(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Get search suggestions."""
        try:
            query = arguments["query"]

            search_service = SearchService()
            suggestions = await search_service.suggest(query)

            content = [TextContent(type="text", text=f"Suggestions for '{query}':")]

            for suggestion in suggestions.get("suggestions", []):
                content.append(TextContent(type="text", text=f"- {suggestion}"))

            return CallToolResult(content=content)
        except Exception as e:
            logger.error(f"Error in _get_suggestions: {e}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error getting suggestions: {str(e)}")],
                isError=True,
            )

    async def _get_resource_viewer(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Get viewer HTML for a resource."""
        try:
            resource_id = arguments["id"]
            embed = arguments.get("embed", False)

            # Build the record URL for the viewer
            base_url = "http://localhost:8000"
            record_url = f"{base_url}/api/v1/resources/{resource_id}/metadata"

            # Create the HTML content
            html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OGM Viewer - Resource {resource_id}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        .viewer-container {{
            width: 100vw;
            height: 100vh;
        }}
        {".viewer-container { height: 600px; }" if embed else ""}
    </style>
</head>
<body>
    <div class="viewer-container">
        <ogm-viewer 
            record-url="{record_url}"
            >
        </ogm-viewer>
    </div>
    
    <!-- Load the OGM Viewer web component -->
    <script type="module" src="https://unpkg.com/ogm-viewer"></script>
</body>
</html>
"""

            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Viewer HTML for resource {resource_id}:\n\n{html_content}",
                    )
                ]
            )
        except Exception as e:
            logger.error(f"Error in _get_resource_viewer: {e}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error getting resource viewer: {str(e)}")],
                isError=True,
            )

    def _public_api_base(self) -> str:
        """Resolve base URL for calling this API over HTTP."""
        base = os.getenv("APPLICATION_URL", "http://localhost:8000").rstrip("/")
        if base.endswith("/api/v1"):
            base = base[: -len("/api/v1")]
        return base

    async def _api_request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        allow_redirects: bool = True,
    ) -> dict[str, Any]:
        """Call the public API and return a structured response."""
        url = f"{self._public_api_base()}/api/v1{path}"
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params, allow_redirects=allow_redirects) as response:
                result: dict[str, Any] = {
                    "status_code": response.status,
                    "url": str(response.url),
                    "content_type": response.headers.get("Content-Type"),
                    "location": response.headers.get("Location"),
                }
                try:
                    result["data"] = await response.json()
                except Exception:
                    result["text"] = await response.text()
                return result

    async def _tool_result_json(
        self, payload: dict[str, Any], is_error: bool = False
    ) -> CallToolResult:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload, indent=2))], isError=is_error
        )

    async def _get_resource_thumbnail(self, arguments: Dict[str, Any]) -> CallToolResult:
        resource_id = arguments.get("id")
        if not resource_id:
            return await self._tool_result_json({"error": "Missing 'id'"}, is_error=True)
        no_cache = bool(arguments.get("no_cache", False))
        suffix = "/thumbnail/no-cache" if no_cache else "/thumbnail"
        payload = await self._api_request(
            f"/resources/{resource_id}{suffix}", allow_redirects=False
        )
        payload["resource_id"] = resource_id
        payload["no_cache"] = no_cache
        return await self._tool_result_json(payload, is_error=payload["status_code"] >= 400)

    async def _get_resource_distributions(self, arguments: Dict[str, Any]) -> CallToolResult:
        resource_id = arguments.get("id")
        if not resource_id:
            return await self._tool_result_json({"error": "Missing 'id'"}, is_error=True)
        payload = await self._api_request(f"/resources/{resource_id}/distributions")
        payload["resource_id"] = resource_id
        return await self._tool_result_json(payload, is_error=payload["status_code"] >= 400)

    async def _get_resource_links(self, arguments: Dict[str, Any]) -> CallToolResult:
        resource_id = arguments.get("id")
        if not resource_id:
            return await self._tool_result_json({"error": "Missing 'id'"}, is_error=True)
        payload = await self._api_request(f"/resources/{resource_id}/links")
        payload["resource_id"] = resource_id
        return await self._tool_result_json(payload, is_error=payload["status_code"] >= 400)

    async def _get_resource_downloads(self, arguments: Dict[str, Any]) -> CallToolResult:
        resource_id = arguments.get("id")
        if not resource_id:
            return await self._tool_result_json({"error": "Missing 'id'"}, is_error=True)
        payload = await self._api_request(f"/resources/{resource_id}/downloads")
        payload["resource_id"] = resource_id
        return await self._tool_result_json(payload, is_error=payload["status_code"] >= 400)

    async def _get_resource_citation(self, arguments: Dict[str, Any]) -> CallToolResult:
        resource_id = arguments.get("id")
        if not resource_id:
            return await self._tool_result_json({"error": "Missing 'id'"}, is_error=True)
        citation_format = (arguments.get("format") or "default").lower()
        path = f"/resources/{resource_id}/citation"
        if citation_format == "json-ld":
            path = f"/resources/{resource_id}/citation/json-ld"
        elif citation_format == "ris":
            path = f"/resources/{resource_id}/citation/ris"
        elif citation_format == "bibtex":
            path = f"/resources/{resource_id}/citation/bibtex"
        payload = await self._api_request(path)
        payload["resource_id"] = resource_id
        payload["format"] = citation_format
        return await self._tool_result_json(payload, is_error=payload["status_code"] >= 400)

    async def _get_search_facet_values(self, arguments: Dict[str, Any]) -> CallToolResult:
        facet_name = arguments.get("facet_name")
        if not facet_name:
            return await self._tool_result_json({"error": "Missing 'facet_name'"}, is_error=True)
        params = {
            "q": arguments.get("q"),
            "page": arguments.get("page", 1),
            "per_page": arguments.get("per_page", 10),
            "sort": arguments.get("sort", "count_desc"),
            "q_facet": arguments.get("q_facet"),
            "adv_q": arguments.get("adv_q"),
        }
        params = {k: v for k, v in params.items() if v is not None}
        payload = await self._api_request(f"/search/facets/{facet_name}", params=params)
        payload["facet_name"] = facet_name
        return await self._tool_result_json(payload, is_error=payload["status_code"] >= 400)

    async def _get_resource_relationships(self, arguments: Dict[str, Any]) -> CallToolResult:
        resource_id = arguments.get("id")
        if not resource_id:
            return await self._tool_result_json({"error": "Missing 'id'"}, is_error=True)
        payload = await self._api_request(f"/resources/{resource_id}/relationships")
        payload["resource_id"] = resource_id
        return await self._tool_result_json(payload, is_error=payload["status_code"] >= 400)

    async def _get_resource_similar_items(self, arguments: Dict[str, Any]) -> CallToolResult:
        resource_id = arguments.get("id")
        if not resource_id:
            return await self._tool_result_json({"error": "Missing 'id'"}, is_error=True)
        payload = await self._api_request(f"/resources/{resource_id}/similar-items")
        payload["resource_id"] = resource_id
        return await self._tool_result_json(payload, is_error=payload["status_code"] >= 400)

    async def _get_resource_static_map(self, arguments: Dict[str, Any]) -> CallToolResult:
        resource_id = arguments.get("id")
        if not resource_id:
            return await self._tool_result_json({"error": "Missing 'id'"}, is_error=True)
        no_cache = bool(arguments.get("no_cache", False))
        suffix = "/static-map/no-cache" if no_cache else "/static-map"
        payload = await self._api_request(
            f"/resources/{resource_id}{suffix}", allow_redirects=False
        )
        payload["resource_id"] = resource_id
        payload["no_cache"] = no_cache
        return await self._tool_result_json(payload, is_error=payload["status_code"] >= 400)

    async def _get_ogm_repos(self, arguments: Dict[str, Any]) -> CallToolResult:
        payload = await self._api_request("/ogm/repos")
        return await self._tool_result_json(payload, is_error=payload["status_code"] >= 400)

    async def _get_ogm_harvest_failures(self, arguments: Dict[str, Any]) -> CallToolResult:
        payload = await self._api_request("/ogm/harvest/failures")
        return await self._tool_result_json(payload, is_error=payload["status_code"] >= 400)

    async def _validate_aardvark_record(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Validate an Aardvark JSON record."""
        try:
            import requests
            from jsonschema import ValidationError, validate

            record = arguments.get("record")
            if not record:
                return CallToolResult(
                    content=[
                        TextContent(type="text", text="Error: No record provided for validation")
                    ],
                    isError=True,
                )

            # Fetch the Aardvark schema from OpenGeoMetadata
            schema_url = "https://opengeometadata.org/schema/geoblacklight-schema-aardvark.json"
            try:
                response = requests.get(schema_url, timeout=10)
                response.raise_for_status()
                schema = response.json()
            except requests.RequestException as e:
                return CallToolResult(
                    content=[
                        TextContent(type="text", text=f"Error: Failed to fetch schema: {str(e)}")
                    ],
                    isError=True,
                )

            # Validate the record against the schema
            errors = []
            warnings = []
            schema_valid = True

            try:
                validate(instance=record, schema=schema)
            except ValidationError as e:
                schema_valid = False
                # Parse validation errors
                for error in e.context:
                    field_path = " -> ".join(str(p) for p in error.path) if error.path else "root"
                    errors.append(f"{field_path}: {error.message}")
                # Also include the main error
                main_field = " -> ".join(str(p) for p in e.path) if e.path else "root"
                errors.append(f"{main_field}: {e.message}")

            # Additional custom validations for Aardvark-specific requirements
            # Check for required fields that might not be in the schema
            required_fields = ["dct_title_s", "gbl_mdVersion_s"]

            for field in required_fields:
                if field not in record or not record[field]:
                    errors.append(
                        f"{field}: This field is required and must be a non-empty string."
                    )

            # Check specific field values
            if "gbl_mdVersion_s" in record and record["gbl_mdVersion_s"] != "Aardvark":
                errors.append("gbl_mdVersion_s: Value must be 'Aardvark'.")

            # Check for common warnings (only if schema validation passed)
            if schema_valid:
                if "dct_description_s" not in record or not record.get("dct_description_s"):
                    warnings.append(
                        "dct_description_s: Description is recommended for better discoverability."
                    )

                if "dcat_bbox" not in record and "solr_geom" not in record:
                    warnings.append(
                        "spatial_coverage: Spatial coverage information is "
                        "recommended (dcat_bbox or solr_geom)."
                    )

            # Determine overall validity
            valid = len(errors) == 0

            # Build the response text
            result_text = f"Validation Result: {'VALID' if valid else 'INVALID'}\n\n"

            if errors:
                result_text += "Errors:\n"
                for error in errors:
                    result_text += f"  - {error}\n"
                result_text += "\n"

            if warnings:
                result_text += "Warnings:\n"
                for warning in warnings:
                    result_text += f"  - {warning}\n"
                result_text += "\n"

            if valid and not warnings:
                result_text += "✅ Record is valid and follows Aardvark schema requirements."

            return CallToolResult(content=[TextContent(type="text", text=result_text)])

        except Exception as e:
            logger.error(f"Error in _validate_aardvark_record: {e}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error validating record: {str(e)}")],
                isError=True,
            )


# Create global service instance
mcp_service = OGMMCPService()


async def run_mcp_server():
    """Run the MCP server via stdio."""
    logger.info("Starting MCP server")
    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("MCP stdio server started, running server")
            # Add timeout to prevent hanging
            await asyncio.wait_for(
                mcp_service.server.run(
                    read_stream,
                    write_stream,
                    InitializationOptions(
                        server_name=MCP_SERVICE_NAME,
                        server_version=MCP_SERVICE_VERSION,
                        capabilities=ServerCapabilities(tools=ToolsCapability()),
                    ),
                ),
                timeout=300,  # 5 minute timeout
            )
    except asyncio.TimeoutError:
        logger.info("MCP server timeout - client may have disconnected")
    except BrokenPipeError:
        logger.info("Client disconnected (broken pipe)")
    except ConnectionResetError:
        logger.info("Client connection reset")
    except Exception as e:
        logger.error(f"Error in MCP server: {e}", exc_info=True)
    finally:
        logger.info("MCP server shutdown complete")


async def run_mcp_websocket_server(websocket):
    """Run the MCP server via WebSocket."""
    try:
        # Handle MCP protocol over WebSocket
        async for message in websocket.iter_text():
            try:
                data = json.loads(message)
                response = await handle_mcp_message(data)
                await websocket.send_text(json.dumps(response))
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps(
                        {"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}}
                    )
                )
            except Exception as e:
                await websocket.send_text(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
                        }
                    )
                )
    except Exception as e:
        logging.error(f"WebSocket error: {e}")


async def handle_mcp_message(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP protocol messages."""
    method = data.get("method")
    msg_id = data.get("id")
    params = data.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": MCP_SERVICE_NAME, "version": MCP_SERVICE_VERSION},
            },
        }

    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": mcp_service.tool_specs}}

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            handler = mcp_service.tool_handlers.get(tool_name)
            if not handler:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {tool_name}"},
                }
            result = await handler(arguments)

            # Convert CallToolResult to JSON-RPC response
            # Handle the case where we have a single JSON response
            if len(result.content) == 1 and hasattr(result.content[0], "text"):
                content_text = result.content[0].text
                # Try to parse as JSON to ensure proper formatting
                try:
                    json.loads(content_text)
                    # If it's valid JSON, return it as-is
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": content_text}],
                            "isError": result.isError if hasattr(result, "isError") else False,
                        },
                    }
                except json.JSONDecodeError:
                    # If it's not JSON, fall back to the original behavior
                    pass

            # Fallback: concatenate all content items
            content_text = ""
            for content_item in result.content:
                if hasattr(content_item, "text"):
                    content_text += content_item.text + "\n"

            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": content_text.strip()}],
                    "isError": result.isError if hasattr(result, "isError") else False,
                },
            }

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": f"Internal error: {str(e)}"},
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


def get_mcp_service_info() -> dict[str, Any]:
    """Build MCP service metadata for the /api/v1/mcp endpoint."""
    tool_names = [tool["name"] for tool in mcp_service.tool_specs]
    tool_docs = {tool["name"]: tool["description"] for tool in mcp_service.tool_specs}
    return {
        "name": MCP_SERVICE_NAME,
        "version": MCP_SERVICE_VERSION,
        "description": MCP_SERVICE_DESCRIPTION,
        "protocol": "mcp",
        "transports": ["stdio", "websocket"],
        "capabilities": {"tools": tool_names},
        "connections": {
            "stdio": {
                "type": "stdio",
                "command": "python",
                "args": ["-m", "app.services.mcp_service"],
            },
            "websocket": {"type": "websocket", "url": "/api/v1/mcp/ws"},
        },
        "documentation": {"tools": tool_docs},
    }


if __name__ == "__main__":
    try:
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        logger.info("MCP server interrupted by user")
    except BrokenPipeError:
        logger.info("MCP server terminated due to broken pipe")
    except Exception as e:
        logger.error(f"Fatal error in MCP server: {e}", exc_info=True)
        sys.exit(1)

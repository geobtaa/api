import asyncio
import json
import logging
import sys
from typing import Any, Dict

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
        self.server = Server("geo-btaa-api")
        self._register_tools()
        logger.info("GeoBTAA MCP Service initialized successfully")

    def _register_tools(self):
        """Register all API endpoints as MCP tools."""
        logger.info("Registering MCP tools")

        @self.server.list_tools()
        async def handle_list_tools() -> ListToolsResult:
            """List all available tools."""
            logger.debug("Handling list_tools request")
            return ListToolsResult(
                tools=[
                    Tool(
                        name="search_resources",
                        description=(
                            "Search for geospatial resources using text queries, "
                            "filters, and sorting options"
                        ),
                        inputSchema={
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
                                    "description": (
                                        "Sort option (relevance, year_desc, year_asc, "
                                        "title_asc, title_desc)"
                                    ),
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
                    ),
                    Tool(
                        name="get_resource",
                        description=(
                            "Get a single geospatial resource by ID with full "
                            "metadata and UI enhancements"
                        ),
                        inputSchema={
                            "type": "object",
                            "properties": {"id": {"type": "string", "description": "Resource ID"}},
                            "required": ["id"],
                        },
                    ),
                    Tool(
                        name="get_resource_ogm",
                        description=("Get just the GeoBTAA Aardvark record for a resource by ID"),
                        inputSchema={
                            "type": "object",
                            "properties": {"id": {"type": "string", "description": "Resource ID"}},
                            "required": ["id"],
                        },
                    ),
                    Tool(
                        name="list_resources",
                        description="List all GeoBTAA resources with pagination",
                        inputSchema={
                            "type": "object",
                            "properties": {
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
                            },
                        },
                    ),
                    Tool(
                        name="get_suggestions",
                        description="Get search suggestions for GeoBTAA autocomplete",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query for GeoBTAA suggestions",
                                }
                            },
                            "required": ["query"],
                        },
                    ),
                    Tool(
                        name="get_resource_viewer",
                        description=(
                            "Get an HTML page with the embedded OGM viewer for a specific resource"
                        ),
                        inputSchema={
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
                    ),
                    Tool(
                        name="validate_aardvark_record",
                        description=(
                            "Validate a single Aardvark JSON record against the GeoBTAA schema"
                        ),
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "record": {
                                    "type": "object",
                                    "description": "The GeoBTAA Aardvark JSON record to validate",
                                }
                            },
                            "required": ["record"],
                        },
                    ),
                ]
            )

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            """Handle tool calls."""
            logger.debug(f"Handling tool call: {name} with arguments: {arguments}")
            try:
                if name == "search_resources":
                    return await self._search_resources(arguments)
                elif name == "get_resource":
                    return await self._get_resource(arguments)
                elif name == "get_resource_ogm":
                    return await self._get_resource_ogm(arguments)
                elif name == "list_resources":
                    return await self._list_resources(arguments)
                elif name == "get_suggestions":
                    return await self._get_suggestions(arguments)
                elif name == "get_resource_viewer":
                    return await self._get_resource_viewer(arguments)
                elif name == "validate_aardvark_record":
                    return await self._validate_aardvark_record(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
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
            resource_id = arguments["id"]

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
                content=[TextContent(type="text", text=f"Error getting resource: {str(e)}")],
                isError=True,
            )

    async def _get_resource_ogm(self, arguments: Dict[str, Any]) -> CallToolResult:
        """Get Aardvark record for a resource."""
        try:
            resource_id = arguments["id"]

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
            logger.error(f"Error in _get_resource_ogm: {e}", exc_info=True)
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error getting resource OGM: {str(e)}")],
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
                content=[TextContent(type="text", text=f"Error listing resources: {str(e)}")],
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
            record_url = f"{base_url}/api/v1/resources/{resource_id}/ogm"

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
                        server_name="ogm-api",
                        server_version="0.1.0",
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
                "serverInfo": {"name": "ogm-api", "version": "0.1.0"},
            },
        }

    elif method == "tools/list":
        tools = [
            {
                "name": "search_resources",
                "description": (
                    "Search for geospatial resources using text queries, "
                    "filters, and sorting options"
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
                "name": "get_resource_ogm",
                "description": "Get just the OpenGeoMetadata Aardvark record for a resource by ID",
                "inputSchema": {
                    "type": "object",
                    "properties": {"id": {"type": "string", "description": "Resource ID"}},
                    "required": ["id"],
                },
            },
            {
                "name": "list_resources",
                "description": "List all geospatial resources with pagination",
                "inputSchema": {
                    "type": "object",
                    "properties": {
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
                    },
                },
            },
            {
                "name": "get_suggestions",
                "description": "Get search suggestions for autocomplete",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query for suggestions"}
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_resource_viewer",
                "description": (
                    "Get an HTML page with the embedded OGM viewer for a specific resource"
                ),
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
                "name": "validate_aardvark_record",
                "description": (
                    "Validate a single Aardvark JSON record against the OpenGeoMetadata schema"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "record": {
                            "type": "object",
                            "description": "The Aardvark JSON record to validate",
                        }
                    },
                    "required": ["record"],
                },
            },
        ]

        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}}

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if tool_name == "search_resources":
                result = await mcp_service._search_resources(arguments)
            elif tool_name == "get_resource":
                result = await mcp_service._get_resource(arguments)
            elif tool_name == "get_resource_ogm":
                result = await mcp_service._get_resource_ogm(arguments)
            elif tool_name == "list_resources":
                result = await mcp_service._list_resources(arguments)
            elif tool_name == "get_suggestions":
                result = await mcp_service._get_suggestions(arguments)
            elif tool_name == "get_resource_viewer":
                result = await mcp_service._get_resource_viewer(arguments)
            elif tool_name == "validate_aardvark_record":
                result = await mcp_service._validate_aardvark_record(arguments)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {tool_name}"},
                }

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

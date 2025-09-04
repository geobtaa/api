import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/mcp")
async def mcp_endpoint():
    """Return MCP service information and connection details."""
    return JSONResponse(
        content={
            "name": "ogm-api",
            "version": "0.1.0",
            "description": "OpenGeoMetadata API MCP Service",
            "protocol": "mcp",
            "transports": ["stdio", "websocket"],
            "capabilities": {
                "tools": [
                    "search_resources",
                    "get_resource",
                    "get_resource_ogm",
                    "list_resources",
                    "get_suggestions",
                    "get_resource_viewer",
                    "validate_aardvark_record",
                ]
            },
            "connections": {
                "stdio": {
                    "type": "stdio",
                    "command": "python",
                    "args": ["-m", "app.services.mcp_service"],
                },
                "websocket": {"type": "websocket", "url": "/api/v1/mcp/ws"},
            },
            "documentation": {
                "tools": {
                    "search_resources": (
                        "Search for geospatial resources using text queries, "
                        "filters, and sorting options"
                    ),
                    "get_resource": (
                        "Get a single geospatial resource by ID with full "
                        "metadata and UI enhancements"
                    ),
                    "get_resource_ogm": (
                        "Get just the OpenGeoMetadata Aardvark record for a resource by ID"
                    ),
                    "list_resources": ("List all geospatial resources with pagination"),
                    "get_suggestions": ("Get search suggestions for autocomplete"),
                    "get_resource_viewer": (
                        "Get an HTML page with the embedded OGM viewer for a specific resource"
                    ),
                    "validate_aardvark_record": (
                        "Validate a single Aardvark JSON record against the OpenGeoMetadata schema"
                    ),
                }
            },
        }
    )


@router.websocket("/mcp/ws")
async def mcp_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for MCP service."""
    await websocket.accept()

    try:
        # Import here to avoid circular imports
        from app.services.mcp_service import run_mcp_websocket_server

        await run_mcp_websocket_server(websocket)
    except WebSocketDisconnect:
        logging.info("MCP WebSocket client disconnected")
    except Exception as e:
        logging.error(f"Error in MCP WebSocket: {e}")
        try:
            await websocket.close()
        except Exception:
            pass

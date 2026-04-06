import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from app.services.mcp_service import get_mcp_service_info

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/mcp")
async def mcp_endpoint():
    """Return MCP service information and connection details."""
    return JSONResponse(content=get_mcp_service_info())


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

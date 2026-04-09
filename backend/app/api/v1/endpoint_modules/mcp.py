import logging

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

from app.services.mcp_service import get_mcp_service_info, handle_mcp_message

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/mcp")
async def mcp_endpoint():
    """Return MCP service information and connection details."""
    return JSONResponse(content=get_mcp_service_info())


@router.post("/mcp")
async def mcp_http_transport(request: Request):
    """Handle JSON-RPC-over-HTTP requests for MCP bridge compatibility."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
        )

    response = await handle_mcp_message(payload)
    if response is None:
        return Response(status_code=204)

    return JSONResponse(content=response)


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

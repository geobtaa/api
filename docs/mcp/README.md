# MCP Service

This directory documents the BTAA Geospatial API's Model Context Protocol (MCP) service and the helper scripts in the repository-level `mcp/` directory.

## Service Overview

The API exposes three MCP-facing transports:

- `GET /api/v1/mcp` returns service metadata, tool listings, and transport details.
- `POST /api/v1/mcp` accepts JSON-RPC requests over HTTP.
- `WS /api/v1/mcp/ws` accepts JSON-RPC requests over WebSocket.

These transports are backed by the MCP service implementation in `backend/app/services/mcp_service.py`.

## Repository Assets

The repository-level `mcp/` directory contains the scripts and templates used by desktop MCP clients:

- `mcp/run_mcp_service.py`
  Runs the stdio MCP server from the repository root.
- `mcp/mcp_http_bridge.js`
  Converts stdio MCP traffic into HTTP `POST /api/v1/mcp` requests.
- `mcp/mcp_websocket_bridge.js`
  Converts stdio MCP traffic into WebSocket traffic against `/api/v1/mcp/ws`.
- `mcp/run_mcp_websocket_bridge.py`
  Launches the WebSocket bridge with a modern Node binary, which is useful when desktop apps resolve `node` to an older NVM version.
- `mcp/claude_mcp_config.json`
  Minimal Claude Desktop starter config.

## Local Development

Start the API first if you want to use one of the bridge scripts:

```bash
docker compose up -d api
```

Run the stdio MCP server directly from the repository root:

```bash
python3 mcp/run_mcp_service.py
```

Run the HTTP bridge:

```bash
node mcp/mcp_http_bridge.js
```

Run the WebSocket bridge:

```bash
node mcp/mcp_websocket_bridge.js
```

Recommended launcher for desktop clients:

```bash
python3 mcp/run_mcp_websocket_bridge.py
```

## Choosing A Transport

- Direct stdio (`mcp/run_mcp_service.py`)
  Best for local development when your Python environment, database, and Elasticsearch are all available on the same machine.
- HTTP bridge (`mcp/mcp_http_bridge.js`)
  Best fallback when the remote API exposes `POST /api/v1/mcp` but WebSocket transport is unavailable or blocked by a proxy.
- WebSocket bridge (`mcp/mcp_websocket_bridge.js`)
  Best general choice for Claude Desktop when the API exposes `/api/v1/mcp/ws`.

## Bridge Environment Variables

Both bridge scripts default to the local API at `http://127.0.0.1:8000`.

- `BTAA_GEOSPATIAL_API_BASE_URL`
  Base URL used to derive MCP endpoints.
- `MCP_SERVER_URL`
  Full HTTP MCP URL override for `mcp/mcp_http_bridge.js`.
- `MCP_HTTP_URL`
  Alias for `MCP_SERVER_URL`.
- `MCP_WEBSOCKET_URL`
  Full WebSocket MCP URL override for `mcp/mcp_websocket_bridge.js`.
- `MCP_NODE_BIN`
  Optional absolute path to a modern Node binary for `mcp/run_mcp_websocket_bridge.py`.

## Claude Desktop

Claude Desktop configuration examples live in [claude_desktop.md](./claude_desktop.md).

The short version:

- Use `mcp/run_mcp_websocket_bridge.py` for local and remote WebSocket-backed setups.
- Use `mcp/mcp_http_bridge.js` if you need an HTTP-only fallback.
- Use `mcp/run_mcp_service.py` only for direct local stdio development.

## Remote Environments

For Kamal deployments such as `dev1` and `dev2`, the base URL should be the public HTTPS origin:

- `https://lib-btaageoapi-dev-app-01.oit.umn.edu`
- `https://lib-geoportal-dev-web-01.oit.umn.edu`

The WebSocket bridge derives:

- `wss://<host>/api/v1/mcp/ws`

The HTTP bridge derives:

- `https://<host>/api/v1/mcp`

## Troubleshooting

- If Claude Desktop starts the bridge with an old Node version and crashes on modern JavaScript syntax, switch to `python3 mcp/run_mcp_websocket_bridge.py`.
- If search-related MCP tools return explicit search errors, verify the API itself can answer `/api/v1/search`.
- If WebSocket transport fails but `POST /api/v1/mcp` works, switch Claude Desktop to the HTTP bridge until the proxy path is fixed.
- If direct stdio works locally but remote access does not, remember that `mcp/run_mcp_service.py` uses the local Python environment, not the remote API.

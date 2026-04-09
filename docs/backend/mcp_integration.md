# MCP Integration

This project already had a backend MCP service in `backend/app/services/mcp_service.py`. The missing pieces from the older `ogm-api` project were the repository-root launcher and the Claude/Desktop bridge scripts.

## What exists now

- `GET /api/v1/mcp` returns MCP service metadata.
- `POST /api/v1/mcp` accepts JSON-RPC messages for the HTTP bridge.
- `WS /api/v1/mcp/ws` accepts JSON-RPC messages for the WebSocket bridge.
- `mcp/run_mcp_service.py` runs the stdio MCP server from the repository root.
- `mcp/mcp_http_bridge.js` proxies stdio JSON-RPC to `POST /api/v1/mcp`.
- `mcp/mcp_websocket_bridge.js` proxies stdio JSON-RPC to `WS /api/v1/mcp/ws`.
- `mcp/run_mcp_websocket_bridge.py` launches the WebSocket bridge with Node 18+ even if a desktop app resolves `node` to an older NVM version.
- `mcp/claude_mcp_config.json` is a template for Claude Desktop: set `cwd` to your local clone root (see below).

## Local usage

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

Recommended for Claude Desktop and machines with multiple Node versions:

```bash
python3 mcp/run_mcp_websocket_bridge.py
```

## Bridge environment variables

Both bridge scripts default to the local API at `http://127.0.0.1:8000`.

- `BTAA_GEOSPATIAL_API_BASE_URL`: Base URL used to derive MCP endpoints.
- `MCP_SERVER_URL`: Full HTTP MCP URL override for `mcp/mcp_http_bridge.js`.
- `MCP_HTTP_URL`: Alias for `MCP_SERVER_URL`.
- `MCP_WEBSOCKET_URL`: Full WebSocket MCP URL override for `mcp/mcp_websocket_bridge.js`.

## Claude Desktop

Copy the `mcpServers` entry from `mcp/claude_mcp_config.json` into your Claude Desktop config (`claude_desktop_config.json`). Set `cwd` to the **absolute path of this repository root** on your machine (for example run `pwd` from the repo root). The `args` path is relative to `cwd`, so it is the same for every clone. The bridge builds `WS /api/v1/mcp/ws` from `BTAA_GEOSPATIAL_API_BASE_URL` (use `https://…` for Kamal dev1/dev2 so the bridge uses `wss://…`).

```json
{
  "mcpServers": {
    "btaa-geospatial-api-local": {
      "command": "python3",
      "args": ["mcp/run_mcp_websocket_bridge.py"],
      "cwd": "/path/to/data-api",
      "env": {
        "BTAA_GEOSPATIAL_API_BASE_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

For a remote API, change `BTAA_GEOSPATIAL_API_BASE_URL` (or add another `mcpServers` entry). Claude Desktop does not expand shell variables inside this JSON, so each environment is usually a separate entry or a hand-edited value.

If you want to force a specific Node binary, set `MCP_NODE_BIN` in the `env` block.

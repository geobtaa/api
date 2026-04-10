# Claude Desktop Configuration

This page contains example `mcpServers` entries for Claude Desktop.

Use these as templates inside your local `claude_desktop_config.json`. Set `cwd` to the absolute path of your clone of this repository.

## Recommended Local WebSocket Setup

This is the best local default if your API is running at `http://127.0.0.1:8000`.

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

## Local Direct Stdio Setup

Use this when you want Claude Desktop to talk directly to the local Python MCP service instead of going through the HTTP or WebSocket bridge.

```json
{
  "mcpServers": {
    "btaa-geospatial-api-local-stdio": {
      "command": "python3",
      "args": ["mcp/run_mcp_service.py"],
      "cwd": "/path/to/data-api",
      "env": {}
    }
  }
}
```

Notes:

- This mode uses your local Python environment directly.
- It is best for development on the same machine as the API dependencies.

## Local HTTP Fallback

Use this if the HTTP MCP endpoint is working but local WebSocket transport is unavailable.

```json
{
  "mcpServers": {
    "btaa-geospatial-api-local-http": {
      "command": "node",
      "args": ["mcp/mcp_http_bridge.js"],
      "cwd": "/path/to/data-api",
      "env": {
        "BTAA_GEOSPATIAL_API_BASE_URL": "http://127.0.0.1:8000"
      }
    }
  }
}
```

If Claude Desktop resolves `node` to an old Node version, replace `"command": "node"` with the absolute path to a newer Node binary.

## Remote `dev1` WebSocket Setup

Use this when you want Claude Desktop to connect to the public `dev1` deployment:

```json
{
  "mcpServers": {
    "btaa-geospatial-api-dev1": {
      "command": "python3",
      "args": ["mcp/run_mcp_websocket_bridge.py"],
      "cwd": "/path/to/data-api",
      "env": {
        "BTAA_GEOSPATIAL_API_BASE_URL": "https://lib-btaageoapi-dev-app-01.oit.umn.edu"
      }
    }
  }
}
```

## Remote `dev1` HTTP Fallback

Use this if you want Claude Desktop to talk to `dev1` over HTTP JSON-RPC instead of WebSocket.

```json
{
  "mcpServers": {
    "btaa-geospatial-api-dev1-http": {
      "command": "node",
      "args": ["mcp/mcp_http_bridge.js"],
      "cwd": "/path/to/data-api",
      "env": {
        "BTAA_GEOSPATIAL_API_BASE_URL": "https://lib-btaageoapi-dev-app-01.oit.umn.edu"
      }
    }
  }
}
```

## Remote `dev2` WebSocket Setup

```json
{
  "mcpServers": {
    "btaa-geospatial-api-dev2": {
      "command": "python3",
      "args": ["mcp/run_mcp_websocket_bridge.py"],
      "cwd": "/path/to/data-api",
      "env": {
        "BTAA_GEOSPATIAL_API_BASE_URL": "https://lib-geoportal-dev-web-01.oit.umn.edu"
      }
    }
  }
}
```

## Multi-Environment Example

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
    },
    "btaa-geospatial-api-dev1": {
      "command": "python3",
      "args": ["mcp/run_mcp_websocket_bridge.py"],
      "cwd": "/path/to/data-api",
      "env": {
        "BTAA_GEOSPATIAL_API_BASE_URL": "https://lib-btaageoapi-dev-app-01.oit.umn.edu"
      }
    },
    "btaa-geospatial-api-dev2": {
      "command": "python3",
      "args": ["mcp/run_mcp_websocket_bridge.py"],
      "cwd": "/path/to/data-api",
      "env": {
        "BTAA_GEOSPATIAL_API_BASE_URL": "https://lib-geoportal-dev-web-01.oit.umn.edu"
      }
    }
  }
}
```

## Tips

- Fully quit and relaunch Claude Desktop after editing `claude_desktop_config.json`.
- Keep `cwd` pointed at the repository root, not the `mcp/` directory.
- Use `MCP_NODE_BIN` if the Python WebSocket launcher should force a specific Node binary:

```json
{
  "MCP_NODE_BIN": "/absolute/path/to/node"
}
```

- If a remote environment exposes `POST /api/v1/mcp` but not WebSocket, switch to the HTTP bridge example.

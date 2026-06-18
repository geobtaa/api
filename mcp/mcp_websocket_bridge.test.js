"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { webSocketOptions } = require("./mcp_websocket_bridge");

test("webSocketOptions includes MCP analytics headers", () => {
  const previousVersion = process.env.BTAA_MCP_CLIENT_VERSION;
  process.env.BTAA_MCP_CLIENT_VERSION = "9.8.7";

  try {
    assert.deepEqual(webSocketOptions(), {
      headers: {
        "User-Agent": "btaa-mcp-websocket-bridge/9.8.7",
        "X-BTAA-Client-Name": "btaa-mcp-websocket-bridge",
        "X-BTAA-Client-Version": "9.8.7",
        "X-BTAA-Client-Channel": "mcp",
      },
    });
  } finally {
    if (previousVersion === undefined) {
      delete process.env.BTAA_MCP_CLIENT_VERSION;
    } else {
      process.env.BTAA_MCP_CLIENT_VERSION = previousVersion;
    }
  }
});

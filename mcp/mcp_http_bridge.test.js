"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { requestHeaders } = require("./mcp_http_bridge");

test("requestHeaders includes JSON and MCP analytics headers", () => {
  const previousVersion = process.env.BTAA_MCP_CLIENT_VERSION;
  process.env.BTAA_MCP_CLIENT_VERSION = "9.8.7";

  try {
    assert.deepEqual(requestHeaders('{"jsonrpc":"2.0"}'), {
      "content-type": "application/json",
      "content-length": 17,
      "User-Agent": "btaa-mcp-http-bridge/9.8.7",
      "X-BTAA-Client-Name": "btaa-mcp-http-bridge",
      "X-BTAA-Client-Version": "9.8.7",
      "X-BTAA-Client-Channel": "mcp",
    });
  } finally {
    if (previousVersion === undefined) {
      delete process.env.BTAA_MCP_CLIENT_VERSION;
    } else {
      process.env.BTAA_MCP_CLIENT_VERSION = previousVersion;
    }
  }
});

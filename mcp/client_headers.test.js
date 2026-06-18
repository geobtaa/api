"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");

const { clientHeaders, clientVersion } = require("./client_headers");

function withEnv(updates, callback) {
  const previous = {};
  for (const key of Object.keys(updates)) {
    previous[key] = process.env[key];
    if (updates[key] === undefined) {
      delete process.env[key];
    } else {
      process.env[key] = updates[key];
    }
  }

  try {
    callback();
  } finally {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = value;
      }
    }
  }
}

test("clientVersion falls back to local", () => {
  withEnv({ BTAA_MCP_CLIENT_VERSION: undefined }, () => {
    assert.equal(clientVersion(), "local");
  });
});

test("clientHeaders returns stable MCP analytics headers", () => {
  withEnv(
    {
      BTAA_MCP_CLIENT_VERSION: "1.2.3",
      BTAA_MCP_CLIENT_INSTANCE: "desktop-1",
    },
    () => {
      assert.deepEqual(clientHeaders("btaa-mcp-http-bridge"), {
        "User-Agent": "btaa-mcp-http-bridge/1.2.3",
        "X-BTAA-Client-Name": "btaa-mcp-http-bridge",
        "X-BTAA-Client-Version": "1.2.3",
        "X-BTAA-Client-Channel": "mcp",
        "X-BTAA-Client-Instance": "desktop-1",
      });
    },
  );
});

test("clientHeaders omits empty client instance", () => {
  withEnv(
    {
      BTAA_MCP_CLIENT_VERSION: "1.2.3",
      BTAA_MCP_CLIENT_INSTANCE: undefined,
    },
    () => {
      assert.equal(clientHeaders("btaa-mcp-http-bridge")["X-BTAA-Client-Instance"], undefined);
    },
  );
});

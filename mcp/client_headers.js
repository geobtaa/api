"use strict";

function clientVersion() {
  return process.env.BTAA_MCP_CLIENT_VERSION || "local";
}

function clientHeaders(clientName) {
  const version = clientVersion();
  const headers = {
    "User-Agent": `${clientName}/${version}`,
    "X-BTAA-Client-Name": clientName,
    "X-BTAA-Client-Version": version,
    "X-BTAA-Client-Channel": "mcp",
  };

  if (process.env.BTAA_MCP_CLIENT_INSTANCE) {
    headers["X-BTAA-Client-Instance"] = process.env.BTAA_MCP_CLIENT_INSTANCE;
  }

  return headers;
}

module.exports = { clientHeaders, clientVersion };

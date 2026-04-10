#!/usr/bin/env node
/**
 * MCP WebSocket bridge for Claude Desktop and other stdio-only MCP clients.
 *
 * This bridge forwards newline-delimited JSON-RPC messages from stdin to the
 * BTAA Geospatial API over WebSocket and writes server messages to stdout.
 */

const readline = require("readline");

function baseUrl() {
  return (process.env.BTAA_GEOSPATIAL_API_BASE_URL || "http://127.0.0.1:8000").replace(
    /\/$/,
    "",
  );
}

function mcpWebSocketUrl() {
  if (process.env.MCP_WEBSOCKET_URL) {
    return process.env.MCP_WEBSOCKET_URL;
  }

  const url = new URL(`${baseUrl()}/api/v1/mcp/ws`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

function getWebSocketImplementation() {
  if (typeof WebSocket === "function") {
    return WebSocket;
  }

  try {
    return require("ws");
  } catch (_error) {
    throw new Error(
      "WebSocket is unavailable. Use Node.js 22+ or install the optional 'ws' package.",
    );
  }
}

function writeJson(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function jsonRpcError(id, code, message) {
  return {
    jsonrpc: "2.0",
    id: id === undefined || id === null ? null : id,
    error: { code, message },
  };
}

function normalizeIncomingPayload(payload) {
  if (typeof payload === "string") {
    return payload;
  }

  if (payload instanceof Buffer) {
    return payload.toString("utf8");
  }

  if (payload instanceof ArrayBuffer) {
    return Buffer.from(payload).toString("utf8");
  }

  if (ArrayBuffer.isView(payload)) {
    return Buffer.from(payload.buffer, payload.byteOffset, payload.byteLength).toString("utf8");
  }

  return String(payload);
}

async function connect() {
  const WebSocketImpl = getWebSocketImplementation();
  const bridgeUrl = mcpWebSocketUrl();

  process.stderr.write(`Using MCP WebSocket bridge -> ${bridgeUrl}\n`);

  return await new Promise((resolve, reject) => {
    const socket = new WebSocketImpl(bridgeUrl);
    let opened = false;

    const onOpen = () => {
      opened = true;
      resolve(socket);
    };

    const onMessage = (eventOrData) => {
      const payload =
        eventOrData && Object.prototype.hasOwnProperty.call(eventOrData, "data")
          ? eventOrData.data
          : eventOrData;
      process.stdout.write(`${normalizeIncomingPayload(payload).trim()}\n`);
    };

    const onError = (error) => {
      const reason = error && error.message ? error.message : String(error);
      if (!opened) {
        reject(new Error(reason));
        return;
      }

      process.stderr.write(`MCP WebSocket bridge error: ${reason}\n`);
    };

    const onClose = () => {
      process.stderr.write("MCP WebSocket bridge disconnected\n");
      process.exit(0);
    };

    if (typeof socket.addEventListener === "function") {
      socket.addEventListener("open", onOpen);
      socket.addEventListener("message", onMessage);
      socket.addEventListener("error", onError);
      socket.addEventListener("close", onClose);
    } else {
      socket.on("open", onOpen);
      socket.on("message", onMessage);
      socket.on("error", onError);
      socket.on("close", onClose);
    }
  });
}

async function main() {
  process.stdin.setEncoding("utf8");
  const socket = await connect();

  const rl = readline.createInterface({
    input: process.stdin,
    crlfDelay: Infinity,
  });

  rl.on("line", (line) => {
    if (!line.trim()) {
      return;
    }

    try {
      JSON.parse(line);
      socket.send(line);
    } catch (_error) {
      writeJson(jsonRpcError(null, -32700, "Parse error"));
    }
  });
  rl.on("close", () => socket.close());

  process.on("SIGINT", () => socket.close());
  process.on("SIGTERM", () => socket.close());

  await new Promise((resolve) => rl.on("close", resolve));
}

main().catch((error) => {
  process.stderr.write(`MCP WebSocket bridge failed: ${error.stack || error.message}\n`);
  process.exit(1);
});

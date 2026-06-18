#!/usr/bin/env node
/**
 * MCP HTTP bridge for Claude Desktop and other stdio-only MCP clients.
 *
 * This bridge forwards newline-delimited JSON-RPC messages from stdin to the
 * BTAA Geospatial API over HTTP POST and writes JSON-RPC responses to stdout.
 */

const http = require("http");
const https = require("https");
const readline = require("readline");

const { clientHeaders } = require("./client_headers");

const CLIENT_NAME = "btaa-mcp-http-bridge";

function baseUrl() {
  return (process.env.BTAA_GEOSPATIAL_API_BASE_URL || "http://127.0.0.1:8000").replace(
    /\/$/,
    "",
  );
}

function mcpHttpUrl() {
  return process.env.MCP_SERVER_URL || process.env.MCP_HTTP_URL || `${baseUrl()}/api/v1/mcp`;
}

function requestHeaders(requestBody) {
  return {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(requestBody),
    ...clientHeaders(CLIENT_NAME),
  };
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

async function postMessage(message) {
  return await new Promise((resolve, reject) => {
    const target = new URL(mcpHttpUrl());
    const requestBody = JSON.stringify(message);
    const transport = target.protocol === "https:" ? https : http;

    const request = transport.request(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port || (target.protocol === "https:" ? 443 : 80),
        path: `${target.pathname}${target.search}`,
        method: "POST",
        headers: requestHeaders(requestBody),
      },
      (response) => {
        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          body += chunk;
        });
        response.on("end", () => {
          if (!body.trim()) {
            resolve(null);
            return;
          }

          try {
            resolve(JSON.parse(body));
          } catch (error) {
            reject(new Error(`Invalid JSON response from ${mcpHttpUrl()}: ${error.message}`));
          }
        });
      },
    );

    request.on("error", reject);
    request.write(requestBody);
    request.end();
  });
}

async function handleLine(line) {
  if (!line.trim()) {
    return;
  }

  let message;
  try {
    message = JSON.parse(line);
  } catch (_error) {
    writeJson(jsonRpcError(null, -32700, "Parse error"));
    return;
  }

  try {
    const response = await postMessage(message);
    if (response) {
      writeJson(response);
    }
  } catch (error) {
    writeJson(jsonRpcError(message.id, -32603, `Internal error: ${error.message}`));
  }
}

async function main() {
  process.stdin.setEncoding("utf8");
  process.stderr.write(`Using MCP HTTP bridge -> ${mcpHttpUrl()}\n`);

  const rl = readline.createInterface({
    input: process.stdin,
    crlfDelay: Infinity,
  });

  let queue = Promise.resolve();
  rl.on("line", (line) => {
    queue = queue.then(() => handleLine(line));
  });

  await new Promise((resolve) => rl.on("close", resolve));
  await queue;
}

if (require.main === module) {
  main().catch((error) => {
    process.stderr.write(`MCP HTTP bridge failed: ${error.stack || error.message}\n`);
    process.exit(1);
  });
}

module.exports = {
  baseUrl,
  handleLine,
  jsonRpcError,
  main,
  mcpHttpUrl,
  postMessage,
  requestHeaders,
};

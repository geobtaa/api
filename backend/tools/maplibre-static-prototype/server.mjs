// Private service. Do not expose this port publicly. Celery owns scheduling/retries.
import http from "node:http";
import { spawn } from "node:child_process";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
const style =
  process.env.STATIC_MAP_STYLE_URL ||
  "https://tiles.openfreemap.org/styles/liberty";
if (new URL(style).hostname !== "tiles.openfreemap.org")
  throw new Error(
    "This renderer currently supports OpenFreeMap styles/attribution only",
  );
let busy = false;
http
  .createServer(async (req, res) => {
    if (req.method === "GET" && req.url === "/health") {
      res.end("ok");
      return;
    }
    if (req.method !== "POST" || req.url !== "/render") {
      res.writeHead(404).end();
      return;
    }
    if (busy) {
      res.writeHead(503, { "Retry-After": "3" }).end("Renderer busy");
      return;
    }
    busy = true;
    let dir;
    try {
      const chunks = [];
      let size = 0;
      for await (const chunk of req) {
        size += chunk.length;
        if (size > 2 * 1024 * 1024) throw new Error("Request too large");
        chunks.push(chunk);
      }
      const input = JSON.parse(Buffer.concat(chunks));
      if (
        ![input.width, input.height].every(
          (n) => Number.isInteger(n) && n >= 64 && n <= 1600,
        )
      )
        throw new Error("Invalid dimensions");
      if (
        !input.bounds &&
        (!Array.isArray(input.center) ||
          input.center.length !== 2 ||
          !input.center.every(Number.isFinite) ||
          Math.abs(input.center[0]) > 180 ||
          Math.abs(input.center[1]) > 85.05112878 ||
          !Number.isFinite(input.leafletZoom) ||
          input.leafletZoom < 1 ||
          input.leafletZoom > 20)
      )
        throw new Error("Invalid camera");
      if (
        input.geometry &&
        ![
          "Polygon",
          "MultiPolygon",
          "LineString",
          "MultiLineString",
          "Point",
          "MultiPoint",
          "GeometryCollection",
        ].includes(input.geometry.type)
      )
        throw new Error("Invalid geometry");
      // Only accept data/camera; clients cannot choose remote style/source URLs.
      const spec = {
        style,
        width: input.width,
        height: input.height,
        bounds: input.bounds,
        center: input.center,
        leafletZoom: input.leafletZoom,
        geometry: input.geometry,
      };
      dir = await mkdtemp(join(tmpdir(), "ogm-render-"));
      await writeFile(join(dir, "spec.json"), JSON.stringify(spec));
      await new Promise((resolve, reject) => {
        const child = spawn(
          process.execPath,
          ["render.mjs", join(dir, "spec.json"), join(dir, "map.png")],
          { stdio: ["ignore", "ignore", "pipe"] },
        );
        let error = "";
        child.stderr.on("data", (b) => {
          error = (error + b).slice(-4000);
        });
        const timer = setTimeout(() => child.kill("SIGKILL"), 65000);
        child.on("error", (e) => {
          clearTimeout(timer);
          reject(e);
        });
        child.on("close", (code) => {
          clearTimeout(timer);
          code === 0
            ? resolve()
            : reject(new Error(error || `Renderer exit ${code}`));
        });
      });
      const png = await readFile(join(dir, "map.png"));
      res
        .writeHead(200, {
          "Content-Type": "image/png",
          "Cache-Control": "no-store",
        })
        .end(png);
    } catch (error) {
      console.error(error.message);
      res
        .writeHead(502, { "Cache-Control": "no-store" })
        .end("Map rendering failed");
    } finally {
      if (dir) await rm(dir, { recursive: true, force: true });
      busy = false;
    }
  })
  .listen(8080, "0.0.0.0");

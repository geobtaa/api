import mbgl from "@maplibre/maplibre-gl-native";
import sharp from "sharp";
import { readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";

export function fitBounds(
  [west, south, east, north],
  width,
  height,
  padding = 48,
) {
  if (
    ![west, south, east, north].every(Number.isFinite) ||
    west >= east ||
    south >= north ||
    south < -85.05112878 ||
    north > 85.05112878
  )
    throw new Error("Invalid or crossing bounds: normalize before rendering");
  const y = (lat) =>
    (1 - Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) / Math.PI) / 2;
  const middleY = (y(south) + y(north)) / 2;
  return {
    center: [
      (west + east) / 2,
      (Math.atan(Math.sinh(Math.PI * (1 - 2 * middleY))) * 180) / Math.PI,
    ],
    zoom: Math.min(
      20,
      Math.log2((width - 2 * padding) / ((512 * (east - west)) / 360)),
      Math.log2((height - 2 * padding) / (512 * (y(south) - y(north)))),
    ),
  };
}

export async function render(spec, output) {
  const started = Date.now();
  const errors = [];
  let requests = 0,
    bytes = 0,
    active = 0;
  const queue = [];
  const controller = new AbortController();
  const timer = setTimeout(
    () => controller.abort(new Error("Render exceeded 60 seconds")),
    60000,
  );
  const download = async (url) => {
    const response = await fetch(url, {
      headers: { "User-Agent": "OpenGeoMetadata-API-StaticMaps/1.0 (https://opengeometadata.org/)" },
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${url}`);
    const data = Buffer.from(await response.arrayBuffer());
    requests++;
    bytes += data.length;
    if (requests > 3000 || bytes > 50 * 1024 * 1024)
      throw new Error("Prototype download budget exceeded");
    return data;
  };
  const pump = () => {
    while (active < 4 && queue.length) {
      const { req, callback } = queue.shift();
      active++;
      download(req.url)
        .then(
          (data) => callback(null, { data }),
          (error) => {
            errors.push(error.message);
            callback(error);
          },
        )
        .finally(() => {
          active--;
          pump();
        });
    }
  };
  let map;
  const onMessage = (message) => {
    if (message.severity === "ERROR") errors.push(message.text);
  };
  mbgl.on("message", onMessage);
  try {
    const style = JSON.parse(await download(spec.style));
    if (spec.geometry) {
      style.sources["ogm-geometry"] = {
        type: "geojson",
        data: { type: "Feature", properties: {}, geometry: spec.geometry },
      };
      style.layers.push(
        {
          id: "ogm-fill",
          type: "fill",
          source: "ogm-geometry",
          paint: { "fill-color": "#2563eb", "fill-opacity": 0.06 },
        },
        {
          id: "ogm-line",
          type: "line",
          source: "ogm-geometry",
          paint: {
            "line-color": "#2563eb",
            "line-width": 3,
            "line-opacity": 0.85,
          },
        },
      );
    }
    if (spec.geometry)
      style.layers.push({
        id: "ogm-point",
        type: "circle",
        source: "ogm-geometry",
        filter: ["==", "$type", "Point"],
        paint: {
          "circle-radius": 5,
          "circle-color": "#2563eb",
          "circle-stroke-color": "#ffffff",
          "circle-stroke-width": 2,
        },
      });
    map = new mbgl.Map({
      ratio: 1,
      request(req, callback) {
        queue.push({ req, callback });
        pump();
      },
    });
    map.load(style);
    const camera = spec.bounds
      ? fitBounds(spec.bounds, spec.width, spec.height)
      : { center: spec.center, zoom: spec.leafletZoom - 1 };
    const pixels = await new Promise((resolve, reject) =>
      map.render(
        { ...camera, width: spec.width, height: spec.height },
        (error, data) => (error ? reject(error) : resolve(data)),
      ),
    );
    if (errors.length) throw new Error(errors.join("\n"));
    // Native rendering has no DOM attribution control; burn credits into the asset.
    const compact = spec.width < 500;
    const footer = Buffer.from(
      `<svg width="${spec.width}" height="${compact ? 36 : 24}"><rect width="100%" height="100%" fill="white" fill-opacity="0.94"/>${compact
        ? `<text x="8" y="14" font-family="sans-serif" font-size="12" fill="#243746">OpenFreeMap · © OpenMapTiles</text><text x="8" y="29" font-family="sans-serif" font-size="12" fill="#243746">© OpenStreetMap contributors</text>`
        : `<text x="${spec.width - 8}" y="17" text-anchor="end" font-family="sans-serif" font-size="12" fill="#243746">OpenFreeMap · © OpenMapTiles · © OpenStreetMap contributors</text>`}</svg>`,
    );
    const png = await sharp(pixels, {
      raw: { width: spec.width, height: spec.height, channels: 4 },
    })
      .composite([{ input: footer, gravity: "south" }])
      .png()
      .toBuffer();
    await writeFile(output, png);
    const manifest = {
      renderer: "maplibre-native-6.4.1-prototype-v1",
      spec,
      camera,
      requests,
      downloadedBytes: bytes,
      durationMs: Date.now() - started,
      sha256: createHash("sha256").update(png).digest("hex"),
      sourceSignature: createHash("sha256")
        .update(
          JSON.stringify({
            renderer: "maplibre-native-6.4.1-prototype-v1",
            spec,
            style,
          }),
        )
        .digest("hex"),
    };
    await writeFile(`${output}.json`, JSON.stringify(manifest, null, 2));
    return manifest;
  } finally {
    clearTimeout(timer);
    controller.abort();
    map?.release();
    mbgl.off("message", onMessage);
  }
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const [input, output] = process.argv.slice(2);
  if (!input || !output)
    throw new Error("Usage: node render.mjs spec.json output.png");
  console.log(
    JSON.stringify(
      await render(JSON.parse(await readFile(input, "utf8")), output),
      null,
      2,
    ),
  );
}

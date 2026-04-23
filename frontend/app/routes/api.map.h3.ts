import type { LoaderFunctionArgs } from "react-router";
import { serverFetchJsonWithTheme } from "../lib/server-api";
import type { MapH3ResponseRaw } from "../../src/services/api";

/**
 * SSR-served map H3 hex aggregation (resource route).
 *
 * The browser requests:
 * /map/h3?q=...&bbox=...&resolution=...&adv_q=...&include_filters[...]=...
 * The SSR server fetches from the upstream API using the server-only API key and returns JSON.
 * This ensures the client does not hit rate limits for hex map requests.
 *
 * Aggressive caching: hex data changes only on reindex. Long TTL reduces load.
 * Responses are gzip'd when the client sends Accept-Encoding: gzip and payload is large enough.
 */
const MAP_H3_BROWSER_MAX_AGE = 300; // Repeat exact-query visits should hit browser cache
const MAP_H3_S_MAXAGE = 86400; // 24 hours CDN/shared cache
const MAP_H3_STALE_WHILE_REVALIDATE = 86400; // Serve stale up to 24h while revalidating
const MAP_H3_GZIP_MIN_BYTES = 1024; // Only gzip if uncompressed body >= this (avoid overhead for tiny responses)

export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);

  const q = url.searchParams.get("q") ?? "";
  const bbox = url.searchParams.get("bbox");
  const resolution = url.searchParams.get("resolution") ?? "5";

  const upstreamPath = "/map/h3";
  const upstreamUrl = new URL(upstreamPath, "http://placeholder");
  upstreamUrl.searchParams.set("q", q);
  if (bbox) upstreamUrl.searchParams.set("bbox", bbox);
  upstreamUrl.searchParams.set("resolution", resolution);

  // Forward advanced query and filter params so the map stays aligned with search results.
  url.searchParams.forEach((value, key) => {
    if (
      key !== "q" &&
      key !== "bbox" &&
      key !== "resolution" &&
      (key === "adv_q" ||
        key.startsWith("include_filters[") ||
        key.startsWith("exclude_filters[") ||
        key.startsWith("fq["))
    ) {
      upstreamUrl.searchParams.append(key, value);
    }
  });

  try {
    const pathAndQuery = `${upstreamPath}${upstreamUrl.search}`;
    const data = await serverFetchJsonWithTheme<MapH3ResponseRaw>(
      request,
      pathAndQuery
    );

    // Do not cache empty hex responses (may be transient or error-derived)
    const cacheControl =
      !data.hexes || data.hexes.length === 0
        ? "no-store"
        : `public, max-age=${MAP_H3_BROWSER_MAX_AGE}, s-maxage=${MAP_H3_S_MAXAGE}, stale-while-revalidate=${MAP_H3_STALE_WHILE_REVALIDATE}`;
    const acceptEncoding = request.headers.get("Accept-Encoding") ?? "";
    const wantsGzip = /gzip/i.test(acceptEncoding);

    const jsonString = JSON.stringify(data);
    const jsonBytes = new TextEncoder().encode(jsonString);

    if (wantsGzip && jsonBytes.length >= MAP_H3_GZIP_MIN_BYTES) {
      const { gzipSync } = await import("node:zlib");
      const gzipped = gzipSync(jsonBytes, { level: 6 });
      return new Response(gzipped, {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Content-Encoding": "gzip",
          "Cache-Control": cacheControl,
          "Vary": "Accept-Encoding",
        },
      });
    }

    return Response.json(data, {
      headers: {
        "Cache-Control": cacheControl,
        "Vary": "Accept-Encoding",
      },
    });
  } catch (error) {
    console.error("Map H3 proxy error:", error);
    if (error instanceof Response) {
      return error;
    }
    return new Response("Failed to fetch map hex data", { status: 500 });
  }
}

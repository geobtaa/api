import type { LoaderFunctionArgs } from "react-router";
import { serverFetchWithTheme } from "../lib/server-api";

/**
 * SSR-served homepage blog cards.
 *
 * Browser requests: /home/blog-posts?limit=...&theme=...&pinned_slugs=...
 * Server forwards to API with server-side auth headers and returns JSON.
 */
export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const upstreamPath = "/home/blog-posts";
  const upstreamUrl = new URL(upstreamPath, "http://placeholder");

  ["limit", "theme", "tag"].forEach((key) => {
    const value = url.searchParams.get(key);
    if (value) upstreamUrl.searchParams.set(key, value);
  });

  url.searchParams.getAll("pinned_slugs").forEach((slug) => {
    if (slug) upstreamUrl.searchParams.append("pinned_slugs", slug);
  });

  try {
    const upstream = await serverFetchWithTheme(
      request,
      `${upstreamPath}${upstreamUrl.search}`,
      {
        headers: { Accept: "application/vnd.api+json, application/json" },
      },
    );

    const body = await upstream.arrayBuffer();
    const headers = new Headers(upstream.headers);
    headers.delete("content-encoding");
    headers.delete("content-length");
    headers.delete("etag");
    if (!headers.get("content-type")) {
      headers.set("content-type", "application/json");
    }
    // This proxy route is primarily a local frontend-dev fallback.
    // Avoid letting it become an extra shared-cache layer that can drift
    // from the canonical same-origin API route.
    headers.set("cache-control", "no-store");
    return new Response(body, { status: upstream.status, headers });
  } catch (error) {
    console.error("Home blog proxy error:", error);
    if (error instanceof Response) {
      return error;
    }
    return new Response("Failed to fetch home blog posts", { status: 500 });
  }
}

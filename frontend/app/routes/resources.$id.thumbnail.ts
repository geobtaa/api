import type { LoaderFunctionArgs } from "react-router";
import { proxyUpstreamResponse } from "../lib/proxy-response";
import { serverFetch } from "../lib/server-api";

function toBrowserThumbnailLocation(requestUrl: URL, location: string): string {
  if (!location.startsWith("/api/v1/thumbnails/")) {
    return location;
  }

  const isLocalDev =
    requestUrl.hostname === "localhost" || requestUrl.hostname === "127.0.0.1";

  if (!isLocalDev) {
    return location;
  }

  return `http://localhost:8000${location}`;
}

/**
 * SSR-served resource thumbnail (resource route).
 *
 * The browser requests: /resources/:id/thumbnail
 * The SSR server fetches from the API using the server-only API key and returns image bytes.
 * This endpoint may return:
 * - A redirect to /api/v1/thumbnails/{hash} if thumbnail is ready
 * - An SVG placeholder if thumbnail is not ready yet
 * - The actual image if the endpoint returns it directly
 */
export async function loader({ params, request }: LoaderFunctionArgs) {
  const { id } = params as { id?: string };
  if (!id) throw new Response("resource id is required", { status: 400 });

  const accept = request.headers.get("accept") || "image/*,*/*;q=0.8";
  const url = new URL(request.url);
  const query = url.search ? url.search : "";
  const upstream = await serverFetch(`/resources/${id}/thumbnail${query}`, {
    headers: { Accept: accept },
    redirect: "manual",
  });

  // Handle redirects (302) - pass through to browser with transformed URL
  if (upstream.status === 302 || upstream.status === 301) {
    const location = upstream.headers.get("location");
    if (location) {
      let redirectUrl = location;

      if (location.startsWith("http://") || location.startsWith("https://")) {
        try {
          const u = new URL(location);
          if (u.pathname.startsWith("/api/v1/thumbnails/")) {
            redirectUrl = toBrowserThumbnailLocation(url, u.pathname + u.search);
          }
        } catch {
          // If URL parsing fails, use as-is.
        }
      } else if (location.startsWith("/api/v1/thumbnails/")) {
        redirectUrl = toBrowserThumbnailLocation(url, location);
      }

      return new Response(null, {
        status: upstream.status,
        headers: {
          Location: redirectUrl,
          "Cache-Control": upstream.headers.get("cache-control") || "no-store",
        },
      });
    }
  }

  return proxyUpstreamResponse(upstream);
}

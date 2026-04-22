import type { LoaderFunctionArgs } from "react-router";
import { serverFetch } from "../lib/server-api";

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
      // Transform the redirect location to use SSR route if it's a thumbnail hash
      let redirectUrl = location;
      // Handle absolute URLs
      if (location.startsWith("http://") || location.startsWith("https://")) {
        try {
          const u = new URL(location);
          if (u.pathname.startsWith("/api/v1/thumbnails/")) {
            redirectUrl = u.pathname.replace("/api/v1/thumbnails/", "/thumbnails/") + u.search;
          }
        } catch {
          // If URL parsing fails, use as-is
        }
      } else if (location.startsWith("/api/v1/thumbnails/")) {
        // Handle relative URLs
        redirectUrl = location.replace("/api/v1/thumbnails/", "/thumbnails/");
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

  const body = await upstream.arrayBuffer();
  const headers = new Headers(upstream.headers);
  headers.delete("content-encoding");
  headers.delete("content-length");

  return new Response(body, { status: upstream.status, headers });
}

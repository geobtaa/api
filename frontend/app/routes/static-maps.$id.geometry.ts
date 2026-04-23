import type { LoaderFunctionArgs } from "react-router";
import { proxyUpstreamResponse } from "../lib/proxy-response";
import { serverFetch } from "../lib/server-api";

function toBrowserStaticMapLocation(requestUrl: URL, location: string): string {
  if (!location.startsWith("/api/v1/static-map-assets/")) {
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
 * SSR-served geometry-overlay static map asset.
 *
 * The browser requests: /static-maps/:id/geometry
 * The SSR server fetches from the API using the server-only API key and returns image bytes.
 */
export async function loader({ params, request }: LoaderFunctionArgs) {
  const { id } = params;
  if (!id) throw new Response("Resource ID is required", { status: 400 });

  const accept = request.headers.get("accept") || "image/*,*/*;q=0.8";
  const url = new URL(request.url);
  const upstream = await serverFetch(`/static-maps/${id}/geometry`, {
    headers: { Accept: accept },
    redirect: "manual",
  });

  if (upstream.status === 302 || upstream.status === 301) {
    const location = upstream.headers.get("location");
    if (location) {
      let redirectUrl = location;

      if (location.startsWith("http://") || location.startsWith("https://")) {
        try {
          const u = new URL(location);
          if (u.pathname.startsWith("/api/v1/static-map-assets/")) {
            redirectUrl = toBrowserStaticMapLocation(url, u.pathname + u.search);
          }
        } catch {
          // Fall back to the upstream location if parsing fails.
        }
      } else if (location.startsWith("/api/v1/static-map-assets/")) {
        redirectUrl = toBrowserStaticMapLocation(url, location);
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

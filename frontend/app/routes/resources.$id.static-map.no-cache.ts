import type { LoaderFunctionArgs } from "react-router";
import { proxyUpstreamResponse } from "../lib/proxy-response";
import { serverFetch } from "../lib/server-api";

/**
 * SSR-served static map image (no-cache variant).
 *
 * The browser requests: /resources/:id/static-map/no-cache
 * The SSR server fetches from the API using the server-only API key and returns image bytes,
 * forcing regeneration of the static map.
 */
export async function loader({ params, request }: LoaderFunctionArgs) {
  const { id } = params;
  if (!id) throw new Response("Resource ID is required", { status: 400 });

  const accept = request.headers.get("accept") || "image/*,*/*;q=0.8";
  const upstream = await serverFetch(`/resources/${id}/static-map/no-cache`, {
    headers: { Accept: accept },
  });

  return proxyUpstreamResponse(upstream);
}

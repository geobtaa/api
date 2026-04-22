import type { LoaderFunctionArgs } from "react-router";
import { proxyUpstreamResponse } from "../lib/proxy-response";
import { serverFetch } from "../lib/server-api";

/**
 * SSR-served resource-class icon on top of the static basemap asset.
 *
 * The browser requests: /static-maps/:id/resource-class-icon
 * The SSR server fetches from the API using the server-only API key and returns image bytes.
 */
export async function loader({ params, request }: LoaderFunctionArgs) {
  const { id } = params;
  if (!id) throw new Response("Resource ID is required", { status: 400 });

  const accept = request.headers.get("accept") || "image/*,*/*;q=0.8";
  const upstream = await serverFetch(`/static-maps/${id}/resource-class-icon`, {
    headers: { Accept: accept },
  });

  return proxyUpstreamResponse(upstream);
}

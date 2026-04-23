import type { LoaderFunctionArgs } from "react-router";
import { proxyUpstreamResponse } from "../lib/proxy-response";
import { serverFetch } from "../lib/server-api";

/**
 * SSR-served resource thumbnail (no-cache variant).
 *
 * The browser requests: /resources/:id/thumbnail/no-cache
 * The SSR server fetches from the API using the server-only API key and returns image bytes,
 * bypassing cached thumbnails so you can see what would be generated.
 */
export async function loader({ params, request }: LoaderFunctionArgs) {
  const { id } = params as { id?: string };
  if (!id) throw new Response("resource id is required", { status: 400 });

  const accept = request.headers.get("accept") || "image/*,*/*;q=0.8";
  const upstream = await serverFetch(`/resources/${id}/thumbnail/no-cache`, {
    headers: { Accept: accept },
  });

  return proxyUpstreamResponse(upstream);
}

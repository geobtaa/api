import type { LoaderFunctionArgs } from "react-router";
import { proxyUpstreamResponse } from "../lib/proxy-response";
import { serverFetch } from "../lib/server-api";

/**
 * SSR-served thumbnail placeholder (resource route).
 *
 * The browser requests: /thumbnails/placeholder
 * The SSR server fetches from the API using the server-only API key and returns image bytes.
 */
export async function loader({ request }: LoaderFunctionArgs) {
  const accept = request.headers.get("accept") || "image/*,*/*;q=0.8";
  const upstream = await serverFetch(`/thumbnails/placeholder`, {
    headers: { Accept: accept },
  });

  return proxyUpstreamResponse(upstream);
}

import type { LoaderFunctionArgs } from "react-router";
import { proxyUpstreamResponse } from "../lib/proxy-response";
import { serverFetch } from "../lib/server-api";

/**
 * SSR-served thumbnail image (resource route).
 *
 * The browser requests: /thumbnails/:image_hash
 * The SSR server fetches from the API using the server-only API key and returns image bytes.
 */
export async function loader({ params, request }: LoaderFunctionArgs) {
  const { image_hash } = params as { image_hash?: string };
  if (!image_hash) throw new Response("image_hash is required", { status: 400 });

  const accept = request.headers.get("accept") || "image/*,*/*;q=0.8";
  const upstream = await serverFetch(`/thumbnails/${image_hash}`, {
    headers: { Accept: accept },
    redirect: "manual",
  });

  if (upstream.status === 302 || upstream.status === 301) {
    const location = upstream.headers.get("location");
    if (location) {
      return new Response(null, {
        status: upstream.status,
        headers: {
          Location: location,
          "Cache-Control": upstream.headers.get("cache-control") || "no-store",
        },
      });
    }
  }

  return proxyUpstreamResponse(upstream);
}

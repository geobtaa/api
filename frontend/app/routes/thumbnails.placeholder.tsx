import type { LoaderFunctionArgs } from "react-router";
import { serverFetch } from "../lib/server-api";

/**
 * SSR-served thumbnail placeholder.
 *
 * The browser requests: /thumbnails/placeholder
 * The SSR server fetches from the API using the server-only API key and streams the image back.
 */
export async function loader({ request }: LoaderFunctionArgs) {
  const accept = request.headers.get("accept") || "image/*,*/*;q=0.8";
  const upstream = await serverFetch(`/thumbnails/placeholder`, {
    headers: { Accept: accept },
  });

  const headers = new Headers(upstream.headers);
  headers.delete("content-encoding");
  headers.delete("content-length");

  return new Response(upstream.body, { status: upstream.status, headers });
}

export default function ThumbnailPlaceholderRoute() {
  return null;
}


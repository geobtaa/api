import type { LoaderFunctionArgs } from "react-router";
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
  });

  const body = await upstream.arrayBuffer();
  const headers = new Headers(upstream.headers);
  headers.delete("content-encoding");
  headers.delete("content-length");

  return new Response(body, { status: upstream.status, headers });
}


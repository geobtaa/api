import type { LoaderFunctionArgs } from "react-router";
import { serverFetch } from "../lib/server-api";

/**
 * SSR-served thumbnail image.
 *
 * The browser requests: /thumbnails/:image_hash
 * The SSR server fetches from the API using the server-only API key and streams the image back.
 *
 * This keeps thumbnails from being rate-limited by anonymous/IP tiers in the browser.
 */
export async function loader({ params, request }: LoaderFunctionArgs) {
  const { image_hash } = params as { image_hash?: string };
  if (!image_hash) throw new Response("image_hash is required", { status: 400 });

  const accept = request.headers.get("accept") || "image/*,*/*;q=0.8";
  const upstream = await serverFetch(`/thumbnails/${image_hash}`, {
    headers: { Accept: accept },
  });

  // Avoid content decoding issues when Node transparently decompresses upstream.
  const headers = new Headers(upstream.headers);
  headers.delete("content-encoding");
  headers.delete("content-length");

  return new Response(upstream.body, { status: upstream.status, headers });
}

export default function ThumbnailRoute() {
  return null;
}


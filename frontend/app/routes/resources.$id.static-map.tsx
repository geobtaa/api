import type { LoaderFunctionArgs } from "react-router";
import { serverFetch } from "../lib/server-api";

/**
 * SSR-served static map image.
 *
 * The browser requests: /resources/:id/static-map
 * The SSR server fetches from the API using the server-only API key and streams the image back.
 *
 * This avoids exposing the API key to the client while keeping rate limiting enabled.
 */
export async function loader({ params, request }: LoaderFunctionArgs) {
  const { id } = params;
  if (!id) throw new Response("Resource ID is required", { status: 400 });

  const accept = request.headers.get("accept") || "image/*,*/*;q=0.8";
  const upstream = await serverFetch(`/resources/${id}/static-map`, {
    headers: { Accept: accept },
  });

  // Important: sanitize encoding/length headers to avoid browser decode failures when
  // Node's fetch stack transparently decompresses upstream bodies.
  const headers = new Headers(upstream.headers);
  headers.delete("content-encoding");
  headers.delete("content-length");

  return new Response(upstream.body, { status: upstream.status, headers });
}

// Route modules are more reliably included when they have a default export.
// This route is image-only, so it renders nothing.
export default function StaticMapRoute() {
  return null;
}


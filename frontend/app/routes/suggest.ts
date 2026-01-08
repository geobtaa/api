import type { LoaderFunctionArgs } from "react-router";
import { serverFetch } from "../lib/server-api";

/**
 * SSR-served suggestions.
 *
 * The browser requests: /suggest?q=...
 * The SSR server calls the API with the server-only API key and returns the JSON.
 */
export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const q = (url.searchParams.get("q") || "").trim();
  if (!q) {
    return new Response(JSON.stringify({ data: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  const upstream = await serverFetch(`/suggest?q=${encodeURIComponent(q)}&format=json`, {
    headers: { Accept: "application/vnd.api+json, application/json" },
  });

  return upstream;
}


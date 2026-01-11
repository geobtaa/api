import type { LoaderFunctionArgs } from "react-router";
import {
  buildPresentation3ManifestFromImageInfo,
  fetchIiifImageInfo,
  normalizeImageServiceId,
} from "../lib/iiif";

export async function loader({ request }: LoaderFunctionArgs) {
  // Support iframe / cross-origin usage (e.g., sandboxed srcDoc frames).
  // This route is purely a public adapter and is safe to expose via CORS.
  if (request.method.toUpperCase() === "OPTIONS") {
    return new Response(null, {
      status: 204,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
      },
    });
  }

  const url = new URL(request.url);
  const imageService = url.searchParams.get("image_service");

  if (!imageService) {
    throw new Response("Missing required query param: image_service", {
      status: 400,
    });
  }

  // Best-effort safety: only allow http(s).
  if (!/^https?:\/\//i.test(imageService)) {
    throw new Response("image_service must be an http(s) URL", { status: 400 });
  }

  const info = await fetchIiifImageInfo(imageService);
  const imageServiceId = normalizeImageServiceId(imageService, info);

  const manifestId = url.toString();
  const manifest = buildPresentation3ManifestFromImageInfo({
    manifestId,
    imageServiceId,
    info,
  });

  return new Response(JSON.stringify(manifest), {
    headers: {
      "Content-Type": "application/json",
      // Don't cache aggressively; this is a lightweight adapter.
      "Cache-Control": "no-store",
      "Access-Control-Allow-Origin": "*",
    },
  });
}


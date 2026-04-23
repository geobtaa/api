import type { LoaderFunctionArgs } from "@react-router";
import { proxyUpstreamResponse } from "../lib/proxy-response";
import { serverFetch } from "../lib/server-api";
import { getPartnerInstitutionBySlug } from "../../src/constants/partnerInstitutions";

/**
 * SSR-served static map image for homepage partner institution cards.
 */
export async function loader({ params, request }: LoaderFunctionArgs) {
  const { slug } = params;
  if (!slug) throw new Response("Institution slug is required", { status: 400 });

  const institution = getPartnerInstitutionBySlug(slug);
  if (!institution?.campusMap) {
    throw new Response("Institution static map is not available", { status: 404 });
  }

  const accept = request.headers.get("accept") || "image/*,*/*;q=0.8";
  const query = new URLSearchParams({
    lat: String(institution.campusMap.latitude),
    lon: String(institution.campusMap.longitude),
    zoom: String(institution.campusMap.zoom),
  });
  const upstream = await serverFetch(
    `/static-maps/institutions/${slug}?${query.toString()}`,
    {
      headers: { Accept: accept },
    },
  );

  return proxyUpstreamResponse(upstream);
}

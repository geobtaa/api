import type { LoaderFunctionArgs } from "react-router";
import { serverFetchJson } from "../lib/server-api";
import type { FacetValuesResponse } from "../../src/types/api";

/**
 * SSR-served facet values (resource route).
 *
 * The browser requests: /api/search/facets?facetName=...&...
 * The SSR server fetches from the upstream API using the server-only API key and returns JSON.
 * This ensures the client does not hit rate limits for facet interactions.
 */
export async function loader({ request }: LoaderFunctionArgs) {
    const url = new URL(request.url);
    const facetName = url.searchParams.get("facetName");

    if (!facetName) {
        throw new Response("facetName is required", { status: 400 });
    }

    // Construct the upstream URL path
    // The upstream API expects: /search/facets/{facetName}?PARAMS
    // We need to forward relevant query parameters from the client request.
    const upstreamPath = `/search/facets/${facetName}`;
    const upstreamUrl = new URL(upstreamPath, "http://placeholder"); // Base irrelevant for constructing search params

    // Forward all search parameters except 'facetName' (which is part of the path)
    url.searchParams.forEach((value, key) => {
        if (key !== "facetName") {
            upstreamUrl.searchParams.append(key, value);
        }
    });

    try {
        // serverFetchJson uses the BTAA_GEOSPATIAL_API_KEY from env
        // and handles the upstream fetch.
        // Note: serverFetchJson expects a path or full URL.
        // We pass the path + query string.
        const pathAndQuery = `${upstreamPath}${upstreamUrl.search}`;

        const data = await serverFetchJson<FacetValuesResponse>(pathAndQuery);

        // Return the data as JSON
        return Response.json(data);
    } catch (error) {
        console.error("Facet proxy error:", error);
        // Propagate the error status if it's a Response, otherwise 500
        if (error instanceof Response) {
            return error;
        }
        return new Response("Failed to fetch facet values", { status: 500 });
    }
}

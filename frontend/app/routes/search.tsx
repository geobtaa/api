import type { LoaderFunctionArgs } from "react-router";
import { useLoaderData, useSearchParams } from "react-router";
import { SearchPage } from "../../src/pages/SearchPage";
import { serverFetchJson } from "../lib/server-api";
import { parseSearchParams } from "../../src/utils/searchParams";
import type { JsonApiResponse } from "../../src/types/api";

/**
 * Loader function that runs server-side to fetch search results.
 * This runs on the server with the API key from environment variables.
 */
export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const searchParams = url.searchParams;

  // Parse search parameters (same logic as client-side)
  const { query, page, facets, excludeFacets, advancedQuery, hasQueryParam } =
    parseSearchParams(searchParams);

  // Only fetch if we have a query parameter or facets
  if (
    !hasQueryParam &&
    (!facets || facets.length === 0) &&
    (!excludeFacets || excludeFacets.length === 0) &&
    (!advancedQuery || advancedQuery.length === 0)
  ) {
    return { searchResults: null };
  }

  // Build API query string
  const apiParams = new URLSearchParams();
  apiParams.set("format", "json");
  if (query) apiParams.set("q", query);
  if (page) apiParams.set("page", page.toString());
  apiParams.set("per_page", "10");

  // Add facets, exclude facets, advanced query, sort, etc.
  // TODO: Convert facets/excludeFacets/advancedQuery to API query params

  const sort = searchParams.get("sort") || "relevance";
  if (sort) apiParams.set("sort", sort);

  const searchResults = await serverFetchJson<JsonApiResponse>(
    `/search?${apiParams.toString()}`,
  );
  return { searchResults };
}

/**
 * Search page component.
 * Uses loader data for initial server-rendered results.
 * Client-side updates can still use the useSearch hook for interactivity.
 */
export default function Search() {
  const { searchResults } = useLoaderData<typeof loader>();
  // For now, we'll still use the client-side hook for state management
  // but we can pre-populate with server data
  return <SearchPage />;
}

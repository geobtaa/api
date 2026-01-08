import type { LoaderFunctionArgs } from "react-router";
import { useLoaderData, useNavigation } from "react-router";
import { SearchPage } from "../../src/pages/SearchPage";
import { serverFetchJson } from "../lib/server-api";
import type { JsonApiResponse } from "../../src/types/api";

/**
 * Loader function that runs server-side to fetch search results.
 * This runs on the server with the API key from environment variables.
 */
export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const apiParams = new URLSearchParams(url.searchParams);

  // Ensure required defaults for the API request.
  apiParams.set("format", "json");
  apiParams.set("per_page", apiParams.get("per_page") || "10");
  apiParams.set("search_field", apiParams.get("search_field") || "all_fields");

  // Only fetch if we have any search criteria (q param, facets, excludes, adv_q, geo filters, etc.)
  const hasAnyCriteria =
    apiParams.has("q") ||
    apiParams.has("adv_q") ||
    Array.from(apiParams.keys()).some(
      (k) =>
        k.startsWith("include_filters[") ||
        k.startsWith("exclude_filters[") ||
        k.startsWith("fq["),
    );

  if (!hasAnyCriteria) return { searchResults: null };

  const searchResults = await serverFetchJson<JsonApiResponse>(`/search?${apiParams.toString()}`);
  return { searchResults };
}

/**
 * Search page component.
 * Uses loader data (and subsequent revalidation) for all search results.
 */
export default function Search() {
  const { searchResults } = useLoaderData<typeof loader>();
  const navigation = useNavigation();
  const isLoading = navigation.state !== "idle";
  return <SearchPage searchResults={searchResults} isLoading={isLoading} />;
}

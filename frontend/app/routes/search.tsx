import type { LoaderFunctionArgs } from "react-router";
import { useLoaderData, useNavigation } from "react-router";
import { SearchPage } from "../../src/pages/SearchPage";
import { serverFetchJsonWithTheme } from "../lib/server-api";
import type { JsonApiResponse } from "../../src/types/api";
import { useEffect } from "react";
import { useApi } from "../../src/context/ApiContext";
import { getThemeConfigFromRequest } from "../lib/theme.server";

/**
 * Loader function that runs server-side to fetch search results.
 * This runs on the server with the API key from environment variables.
 */
export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const apiParams = new URLSearchParams(url.searchParams);

  // Ensure required defaults for the API request.
  apiParams.set("format", "json");
  const defaultPerPage = apiParams.get("view") === "gallery" ? "20" : "10";
  apiParams.set("per_page", apiParams.get("per_page") || defaultPerPage);
  apiParams.set("search_field", apiParams.get("search_field") || "all_fields");

  // Fetch when we have any search criteria: q (even empty = "show all"), adv_q, or filters.
  // Empty q explicitly means "browse all results" and must trigger a fetch.
  const hasQueryParam = apiParams.has("q");
  const hasFilters =
    apiParams.has("adv_q") ||
    Array.from(apiParams.keys()).some(
      (k) =>
        k.startsWith("include_filters[") ||
        k.startsWith("exclude_filters[") ||
        k.startsWith("fq["),
    );
  const hasAnyCriteria = hasQueryParam || hasFilters;

  if (!hasAnyCriteria) return { searchResults: null };

  // For accurate "Last API Request" display, mirror theme default params in the URL we report.
  const theme = getThemeConfigFromRequest(request);
  (theme.api?.default_query_params || []).forEach((param) => {
    const parsed = new URLSearchParams(param);
    parsed.forEach((value, key) => {
      const existing = apiParams.getAll(key);
      if (existing.includes(value)) return;
      apiParams.append(key, value);
    });
  });

  const searchPath = `/search?${apiParams.toString()}`;
  const searchResults = await serverFetchJsonWithTheme<JsonApiResponse>(
    request,
    searchPath
  );

  // Provide a browser-usable URL for "Last API Request" (same-origin /api/v1).
  const lastApiUrl = `/api/v1${searchPath}`;
  return { searchResults, lastApiUrl };
}

/**
 * Search page component.
 * Uses loader data (and subsequent revalidation) for all search results.
 */
export default function Search() {
  const { searchResults, lastApiUrl } = useLoaderData<typeof loader>();
  const navigation = useNavigation();
  const isLoading = navigation.state !== "idle";
  const { setLastApiUrl } = useApi();

  // Keep footer's "Last API Request" in sync with SSR loader calls without re-fetching in the browser.
  useEffect(() => {
    if (lastApiUrl) setLastApiUrl(lastApiUrl);
  }, [lastApiUrl, setLastApiUrl]);

  return <SearchPage searchResults={searchResults} isLoading={isLoading} />;
}

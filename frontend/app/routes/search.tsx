import type { LoaderFunctionArgs, MetaFunction } from 'react-router';
import { useLoaderData, useNavigation } from 'react-router';
import { SearchPage } from '../../src/pages/SearchPage';
import { useEffect } from 'react';
import { useApi } from '../../src/context/ApiContext';
import { getThemeConfigFromRequest } from '../lib/theme.server';
import { buildSeoMeta } from '../../src/config/seo';
import { SEARCH_RESULTS_PER_PAGE } from '../../src/constants/search';
import { buildSearchPageTitleFromUrl } from '../../src/utils/searchPageTitle';

/**
 * Loader function for the search page shell.
 *
 * Search result data is fetched after hydration through /search/results, which
 * keeps the server-only API key in the BFF while avoiding blocking SSR on
 * facet-heavy API responses.
 */
export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const apiParams = new URLSearchParams(url.searchParams);
  const query = url.searchParams.get('q') || '';

  // Ensure required defaults for the API request.
  apiParams.set('format', 'json');
  apiParams.set('per_page', String(SEARCH_RESULTS_PER_PAGE));
  apiParams.set('search_field', apiParams.get('search_field') || 'all_fields');

  // Fetch when we have any search criteria: q (even empty = "show all"), adv_q, or filters.
  // Empty q explicitly means "browse all results" and must trigger a fetch.
  const hasQueryParam = apiParams.has('q');
  const hasFilters =
    apiParams.has('adv_q') ||
    Array.from(apiParams.keys()).some(
      (k) =>
        k.startsWith('include_filters[') ||
        k.startsWith('exclude_filters[') ||
        k.startsWith('fq[')
    );
  const hasAnyCriteria = hasQueryParam || hasFilters;

  if (!hasAnyCriteria) {
    return {
      searchResults: null,
      lastApiUrl: null,
      clientSearchEnabled: true,
      query,
      currentUrl: url.href,
    };
  }

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

  // Provide a browser-usable URL for "Last API Request" (same-origin /api/v1).
  const lastApiUrl = `/api/v1${searchPath}`;
  return {
    searchResults: null,
    lastApiUrl,
    clientSearchEnabled: true,
    query,
    currentUrl: url.href,
  };
}

export const meta: MetaFunction<typeof loader> = ({ data }) =>
  buildSeoMeta({
    title: data?.currentUrl
      ? buildSearchPageTitleFromUrl(data.currentUrl)
      : data?.query
        ? `Search: ${data.query}`
        : 'Search Results',
    description:
      'Search existing resources in the Big Ten Academic Alliance Geoportal.',
    url: data?.currentUrl,
  });

/**
 * Search page component.
 * Uses the loader for the shell and browser-side /search/results for data.
 */
export default function Search() {
  const { searchResults, lastApiUrl, clientSearchEnabled } =
    useLoaderData<typeof loader>();
  const navigation = useNavigation();
  const isLoading = navigation.state !== 'idle';
  const { setLastApiUrl } = useApi();

  // Keep footer's "Last API Request" in sync before the browser data fetch completes.
  useEffect(() => {
    if (lastApiUrl) setLastApiUrl(lastApiUrl);
  }, [lastApiUrl, setLastApiUrl]);

  return (
    <SearchPage
      searchResults={searchResults}
      isLoading={isLoading}
      clientSearchEnabled={clientSearchEnabled}
    />
  );
}

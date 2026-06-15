import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router';
import { fetchSearchResults } from '../services/api';
import { parseSearchParams } from '../utils/searchParams';
import { useApi } from '../context/ApiContext';
import { debugLog } from '../utils/logger';
import { SEARCH_RESULTS_PER_PAGE } from '../constants/search';
import type { JsonApiResponse } from '../types/api';
import type { AdvancedClause, FacetFilter } from '../types/search';

// Export the interface so it can be used in ResourceView.tsx
export interface SearchState {
  query?: string;
  page?: number;
  facets?: FacetFilter[];
  sort?: string;
}

export function useSearch({ enabled = true }: { enabled?: boolean } = {}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [results, setResults] = useState<JsonApiResponse | null>(null);
  const [resultsKey, setResultsKey] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const { setLastApiUrl } = useApi();
  const sort = searchParams.get('sort') || 'relevance';
  const perPage = SEARCH_RESULTS_PER_PAGE;
  const searchField = searchParams.get('search_field') || 'all_fields';
  const searchParamsKey = searchParams.toString();
  const hasFilterParam = useMemo(
    () =>
      Array.from(searchParams.keys()).some(
        (key) =>
          key.startsWith('include_filters[') ||
          key.startsWith('exclude_filters[') ||
          key.startsWith('fq[')
      ),
    [searchParamsKey, searchParams]
  );

  // Parse search parameters and memoize facets to prevent infinite loops
  const {
    query,
    page,
    facets: rawFacets,
    excludeFacets: rawExclude,
    advancedQuery: rawAdvanced,
    hasQueryParam,
  } = parseSearchParams(searchParams);
  const facetsString = JSON.stringify(rawFacets);
  const facets = useMemo(() => rawFacets, [facetsString]);
  const excludeString = JSON.stringify(rawExclude || []);
  const excludeFacets = useMemo(() => rawExclude || [], [excludeString]);
  const advancedString = JSON.stringify(rawAdvanced || []);
  const advancedQuery = useMemo(
    () => rawAdvanced || [],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rawAdvanced?.length, advancedString]
  );

  useEffect(() => {
    let isCurrentRequest = true;

    debugLog('🔍 useSearch useEffect triggered with:', {
      enabled,
      query,
      page,
      perPage,
      facetsLength: facets?.length,
      excludeLength: excludeFacets?.length,
      hasFilterParam,
      sort,
      searchField,
      advancedClauses: advancedQuery.length,
      setLastApiUrl: typeof setLastApiUrl,
    });

    if (!enabled) {
      setIsLoading(false);
      return () => {
        isCurrentRequest = false;
      };
    }

    // Only fetch if we have a query parameter (even if empty), filters, or advanced clauses.
    // Geo bbox filters are deliberately excluded from `facets`, but still need to trigger search.
    if (
      !hasQueryParam &&
      !hasFilterParam &&
      (!advancedQuery || advancedQuery.length === 0)
    ) {
      debugLog('⏭️ Skipping search - no query, filters, or advanced clauses');
      setResults(null);
      setResultsKey(null);
      setError(null);
      setErrorKey(null);
      setIsLoading(false);
      return () => {
        isCurrentRequest = false;
      };
    }

    debugLog('🚀 Starting search API call...');
    const startTime = performance.now();
    const requestSearchParamsKey = searchParamsKey;

    const fetchResults = async () => {
      setIsLoading(true);
      setError(null);
      setErrorKey(null);

      try {
        const searchResults = await fetchSearchResults(
          query || '', // Pass empty string if query is undefined
          page,
          perPage,
          facets,
          setLastApiUrl,
          sort,
          excludeFacets,
          advancedQuery,
          undefined,
          new URLSearchParams(requestSearchParamsKey)
        );

        if (!isCurrentRequest) return;

        const endTime = performance.now();
        debugLog(
          `✅ Search completed in ${(endTime - startTime).toFixed(2)}ms`
        );
        debugLog(`📊 Results: ${searchResults?.data?.length || 0} items`);

        setResults(searchResults);
        setResultsKey(requestSearchParamsKey);
      } catch (err) {
        if (!isCurrentRequest) return;

        const endTime = performance.now();
        console.error(
          `❌ Search failed after ${(endTime - startTime).toFixed(2)}ms:`,
          err
        );
        setError(err instanceof Error ? err.message : 'An error occurred');
        setErrorKey(requestSearchParamsKey);
        setResults(null);
        setResultsKey(null);
      } finally {
        if (isCurrentRequest) {
          setIsLoading(false);
        }
      }
    };

    fetchResults();

    return () => {
      isCurrentRequest = false;
    };
  }, [
    query,
    page,
    perPage,
    facets,
    excludeFacets,
    advancedQuery,
    sort,
    searchField,
    searchParamsKey,
    hasFilterParam,
    hasQueryParam,
    enabled,
    setLastApiUrl,
  ]);

  const updateSearch = ({
    query,
    page,
    facets,
    sort: newSort,
    excludeFacets: nextExcludeFacets,
    advancedQuery: nextAdvancedQuery,
  }: {
    query?: string;
    page?: number;
    facets?: FacetFilter[];
    excludeFacets?: FacetFilter[];
    advancedQuery?: AdvancedClause[];
    sort?: string;
  }) => {
    const newParams = new URLSearchParams(searchParams);

    if (query !== undefined) {
      // Always set 'q' param, even if empty, to ensure API call is made
      // Empty 'q' will return all results from the API
      newParams.set('q', query);
      newParams.delete('page'); // Reset page when query changes
    }

    if (page !== undefined) {
      if (page > 1) {
        newParams.set('page', page.toString());
      } else {
        newParams.delete('page');
      }
    }

    if (newSort !== undefined) {
      if (newSort !== 'relevance') {
        newParams.set('sort', newSort);
      } else {
        newParams.delete('sort');
      }
    }

    if (facets !== undefined) {
      // Clear existing include filters (preserve geo/bbox and year_range - they use distinct param structures)
      Array.from(newParams.keys())
        .filter(
          (key) =>
            (key.startsWith('include_filters[') || key.startsWith('fq[')) &&
            !key.startsWith('include_filters[geo]') &&
            !key.startsWith('include_filters[year_range]')
        )
        .forEach((key) => newParams.delete(key));

      // Add new include filters
      facets.forEach(({ field, value }) => {
        newParams.append(`include_filters[${field}][]`, value);
      });
    }

    if (nextExcludeFacets !== undefined) {
      // Clear existing exclude filters
      Array.from(newParams.keys())
        .filter((key) => key.startsWith('exclude_filters['))
        .forEach((key) => newParams.delete(key));

      // Add new exclude filters
      nextExcludeFacets.forEach(({ field, value }) => {
        newParams.append(`exclude_filters[${field}][]`, value);
      });
    }

    if (nextAdvancedQuery !== undefined) {
      if (nextAdvancedQuery.length > 0) {
        const serialized = nextAdvancedQuery.map(({ op, field, q }) => ({
          op,
          f: field,
          q,
        }));
        newParams.set('adv_q', JSON.stringify(serialized));
      } else {
        newParams.delete('adv_q');
      }
      newParams.delete('page'); // Reset page when advanced query changes
    }

    setSearchParams(newParams);
  };

  return {
    query,
    results,
    resultsKey,
    searchParamsKey,
    isLoading,
    error,
    errorKey,
    page: page || 1,
    perPage,
    totalResults: results?.meta?.totalCount || 0,
    facets: facets || [],
    excludeFacets: excludeFacets || [],
    advancedQuery: advancedQuery || [],
    updateSearch,
    sort,
  };
}

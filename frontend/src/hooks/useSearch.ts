import { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router';
import { fetchSearchResults } from '../services/api';
import { parseSearchParams } from '../utils/searchParams';
import { useApi } from '../context/ApiContext';
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
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { setLastApiUrl } = useApi();
  const sort = searchParams.get('sort') || 'relevance';
  const view = searchParams.get('view') || 'list';
  const perPageParam = searchParams.get('per_page');
  const parsedPerPage = perPageParam ? parseInt(perPageParam, 10) : NaN;
  const perPage = Number.isFinite(parsedPerPage)
    ? parsedPerPage
    : view === 'gallery'
      ? 20
      : 10;
  const searchField = searchParams.get('search_field') || 'all_fields';
  const searchParamsKey = searchParams.toString();

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
    console.log('🔍 useSearch useEffect triggered with:', {
      enabled,
      query,
      page,
      perPage,
      facetsLength: facets?.length,
      excludeLength: excludeFacets?.length,
      sort,
      searchField,
      advancedClauses: advancedQuery.length,
      setLastApiUrl: typeof setLastApiUrl,
    });

    if (!enabled) {
      setIsLoading(false);
      return;
    }

    // Only fetch if we have a query parameter (even if empty) or facets
    if (
      !hasQueryParam &&
      (!facets || facets.length === 0) &&
      (!excludeFacets || excludeFacets.length === 0) &&
      (!advancedQuery || advancedQuery.length === 0)
    ) {
      console.log('⏭️ Skipping search - no query or facets');
      setResults(null);
      return;
    }

    console.log('🚀 Starting search API call...');
    const startTime = performance.now();

    const fetchResults = async () => {
      setIsLoading(true);
      setError(null);

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
          new URLSearchParams(searchParamsKey)
        );

        const endTime = performance.now();
        console.log(
          `✅ Search completed in ${(endTime - startTime).toFixed(2)}ms`
        );
        console.log(`📊 Results: ${searchResults?.data?.length || 0} items`);

        setResults(searchResults);
      } catch (err) {
        const endTime = performance.now();
        console.error(
          `❌ Search failed after ${(endTime - startTime).toFixed(2)}ms:`,
          err
        );
        setError(err instanceof Error ? err.message : 'An error occurred');
        setResults(null);
      } finally {
        setIsLoading(false);
      }
    };

    fetchResults();
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
    isLoading,
    error,
    page: page || 1,
    perPage: results?.meta?.perPage || perPage,
    totalResults: results?.meta?.totalCount || 0,
    facets: facets || [],
    excludeFacets: excludeFacets || [],
    advancedQuery: advancedQuery || [],
    updateSearch,
    sort,
  };
}

import React, { useEffect, useRef, useState } from 'react';
import { Seo } from '../components/Seo';
import { useSearchParams } from 'react-router';
import { SearchResults } from '../components/SearchResults';
import { Pagination } from '../components/Pagination';
import { ErrorMessage } from '../components/ErrorMessage';
import { SearchConstraints } from '../components/search/SearchConstraints';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import type { AdvancedClause, FacetFilter } from '../types/search';
import { FacetList } from '../components/FacetList';
import { SlidersHorizontal, X } from 'lucide-react';
// import { MapView } from '../components/search/MapView';
import { MapProvider, useMap } from '../context/MapContext';
import { SortControl } from '../components/search/SortControl';
import { ViewToggle, type ViewMode } from '../components/search/ViewToggle';
import { GalleryView } from '../components/search/GalleryView';
import { MapResultView } from '../components/search/MapResultView';
import { AdvancedSearchBuilder } from '../components/search/AdvancedSearchBuilder';
import { LocationFacetCollapsible } from '../components/search/LocationFacetCollapsible';
import { NoResultsSearchHelp } from '../components/search/NoResultsSearchHelp';
import { useFacetAccordion } from '../hooks/useFacetAccordion';
import { useSearch } from '../hooks/useSearch';
import { SEARCH_RESULTS_PER_PAGE } from '../constants/search';
import {
  parseSearchParams,
  normalizeFacetValueForUrl,
} from '../utils/searchParams';
import { formatCount } from '../utils/formatNumber';
import type { JsonApiResponse } from '../types/api';
import {
  generateAnalyticsId,
  scheduleAnalyticsBatch,
  serializeSearchParams,
} from '../services/analytics';

// Stable search identity for analytics. Page and per_page are excluded so a
// paged result set remains part of the same search session.
const getSearchContext = (params: URLSearchParams) => {
  const keys = Array.from(params.keys())
    .filter((k) => k !== 'page' && k !== 'per_page')
    .sort();
  return keys.map((k) => `${k}=${params.getAll(k).sort().join(',')}`).join('&');
};

const DEFAULT_VIEW: ViewMode = 'map';

function isViewMode(value: string | null): value is ViewMode {
  return value === 'map' || value === 'list' || value === 'gallery';
}

type SearchPageProps = {
  // Loader-provided results (SSR/server-side).
  searchResults?: JsonApiResponse | null;
  // Navigation state from the route (client transitions).
  isLoading?: boolean;
  // Enables shell-first browser fetching through the keyed /search/results BFF route.
  clientSearchEnabled?: boolean;
};

// Create a separate component for the search content
function SearchContent({
  searchResults,
  isLoading,
  clientSearchEnabled = false,
}: SearchPageProps) {
  const { hoveredResourceId, hoveredGeometry } = useMap();
  const [searchParams, setSearchParams] = useSearchParams();
  const { accordion, setAccordion } = useFacetAccordion();
  const [isFilterDrawerOpen, setIsFilterDrawerOpen] = useState(false);
  const [hasOpenedFilterDrawer, setHasOpenedFilterDrawer] = useState(false);
  const [isDesktopViewport, setIsDesktopViewport] = useState(false);
  const showAdvancedParam = searchParams.get('showAdvanced') === 'true';
  const {
    query,
    page,
    facets: searchFacets,
    excludeFacets: searchExcludeFacets,
    advancedQuery,
  } = parseSearchParams(searchParams);
  const sort = searchParams.get('sort') || 'relevance';
  const searchField = searchParams.get('search_field') || 'all_fields';
  const viewParam = searchParams.get('view');
  const currentView = isViewMode(viewParam) ? viewParam : DEFAULT_VIEW;
  const normalizedQuery = query || '';
  const currentSearchParamsKey = searchParams.toString();
  const currentContext = getSearchContext(searchParams);
  const hasAnySearchCriteria =
    searchParams.has('q') ||
    searchParams.has('adv_q') ||
    Array.from(searchParams.keys()).some(
      (key) =>
        key.startsWith('include_filters[') ||
        key.startsWith('exclude_filters[') ||
        key.startsWith('fq[')
    );
  const shouldFetchClientSearch = clientSearchEnabled && !searchResults;
  const clientSearch = useSearch({ enabled: shouldFetchClientSearch });
  const hasFreshClientResults =
    clientSearch.resultsKey === currentSearchParamsKey && clientSearch.results;
  const hasCurrentClientError =
    clientSearch.errorKey === currentSearchParamsKey && clientSearch.error;
  const clientRequestSettledForCurrentParams =
    Boolean(hasFreshClientResults) || Boolean(hasCurrentClientError);
  const activeSearchResults =
    searchResults ?? (hasFreshClientResults ? clientSearch.results : null);
  const activeIsLoading =
    Boolean(isLoading) ||
    (shouldFetchClientSearch &&
      hasAnySearchCriteria &&
      (Boolean(clientSearch.isLoading) ||
        !clientRequestSettledForCurrentParams));

  // Ensure ?q= is present if no params are set to trigger default search
  useEffect(() => {
    if (Array.from(searchParams.keys()).length === 0) {
      setSearchParams({ q: '' }, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const perPage = SEARCH_RESULTS_PER_PAGE;
  const searchTotalResults = activeSearchResults?.meta?.totalCount || 0;
  const totalPages = Math.ceil(searchTotalResults / perPage);
  const hasNoSearchResults =
    !activeIsLoading &&
    Boolean(activeSearchResults) &&
    searchTotalResults === 0;
  const shouldShowLocationFacetMap =
    !activeSearchResults || activeIsLoading || searchTotalResults > 0;
  const advancedSearchHref = React.useMemo(() => {
    const next = new URLSearchParams(searchParams);
    if (!next.has('q')) {
      next.set('q', normalizedQuery);
    }
    next.set('showAdvanced', 'true');
    return `/search?${next.toString()}`;
  }, [searchParams, normalizedQuery]);
  const activeFilterCount = React.useMemo(() => {
    const activeFacetKeys = new Set(
      searchFacets.map((facet) =>
        facet.field === 'year_range'
          ? 'year_range'
          : `${facet.field}\0${facet.value}`
      )
    );
    const activeExcludeKeys = new Set(
      searchExcludeFacets.map((facet) => `${facet.field}\0${facet.value}`)
    );
    const hasGeoFilter =
      searchParams.get('include_filters[geo][type]') === 'bbox';

    return (
      activeFacetKeys.size +
      activeExcludeKeys.size +
      advancedQuery.length +
      (hasGeoFilter ? 1 : 0)
    );
  }, [advancedQuery.length, searchFacets, searchExcludeFacets, searchParams]);
  const shouldRenderFilterContent =
    isDesktopViewport || isFilterDrawerOpen || hasOpenedFilterDrawer;

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (typeof window.matchMedia !== 'function') {
      setIsDesktopViewport(true);
      return;
    }

    const mediaQuery = window.matchMedia('(min-width: 1024px)');
    const syncDesktopViewport = () => {
      setIsDesktopViewport(mediaQuery.matches);
    };

    syncDesktopViewport();
    if (typeof mediaQuery.addEventListener === 'function') {
      mediaQuery.addEventListener('change', syncDesktopViewport);
      return () => {
        mediaQuery.removeEventListener('change', syncDesktopViewport);
      };
    }

    mediaQuery.addListener(syncDesktopViewport);
    return () => {
      mediaQuery.removeListener(syncDesktopViewport);
    };
  }, []);

  useEffect(() => {
    if (!isFilterDrawerOpen || typeof document === 'undefined') return;

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isFilterDrawerOpen]);

  useEffect(() => {
    if (!isFilterDrawerOpen || typeof window === 'undefined') return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsFilterDrawerOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isFilterDrawerOpen]);

  // For now, treat API errors as “no results” and let ErrorMessage show when needed.
  const activeSearchError =
    activeSearchResults && 'error' in activeSearchResults
      ? activeSearchResults.error
      : null;
  const resultError = activeSearchError ? String(activeSearchError) : null;
  const error =
    resultError ||
    (shouldFetchClientSearch ? hasCurrentClientError || null : null);

  const searchContextRef = useRef(currentContext);
  const trackedAnalyticsKeysRef = useRef<Set<string>>(new Set());
  const [searchId, setSearchId] = useState(() => generateAnalyticsId('search'));

  useEffect(() => {
    if (searchContextRef.current === currentContext) return;
    searchContextRef.current = currentContext;
    trackedAnalyticsKeysRef.current = new Set();
    setSearchId(generateAnalyticsId('search'));
  }, [currentContext]);

  const shouldShowSearchingPlaceholder =
    !error && hasAnySearchCriteria && !activeSearchResults && !activeIsLoading;

  // Restore view preference whenever URL lacks a view param.
  // This keeps preferred layout sticky even when new searches navigate to /search?q=...
  useEffect(() => {
    if (searchParams.has('view')) return;

    const savedView = localStorage.getItem(
      'b1g_view_preference'
    ) as ViewMode | null;
    if (!isViewMode(savedView)) return;

    const next = new URLSearchParams(searchParams);
    if (Array.from(next.keys()).length === 0) {
      next.set('q', '');
    }

    if (savedView !== DEFAULT_VIEW) {
      next.set('view', savedView);
    } else {
      next.delete('view');
    }

    if (
      next.has('per_page') &&
      next.get('per_page') !== String(SEARCH_RESULTS_PER_PAGE)
    ) {
      next.set('per_page', String(SEARCH_RESULTS_PER_PAGE));
    }

    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const updateSearch = ({
    query,
    page,
    facets,
    sort: newSort,
    excludeFacets: nextExcludeFacets,
    advancedQuery: nextAdvancedQuery,
    view,
    perPage,
  }: {
    query?: string;
    page?: number;
    facets?: FacetFilter[];
    excludeFacets?: FacetFilter[];
    advancedQuery?: AdvancedClause[];
    sort?: string;
    view?: ViewMode;
    perPage?: number;
  }) => {
    const newParams = new URLSearchParams(searchParams);

    if (query !== undefined) {
      // Always set 'q' param, even if empty, to ensure loader is invoked.
      newParams.set('q', query);
      newParams.delete('page'); // Reset page when query changes
    }

    if (page !== undefined) {
      if (page > 1) newParams.set('page', page.toString());
      else newParams.delete('page');
    }

    if (newSort !== undefined) {
      if (newSort !== 'relevance') newParams.set('sort', newSort);
      else newParams.delete('sort');
    }

    if (view !== undefined) {
      // Save preference
      localStorage.setItem('b1g_view_preference', view);

      if (view !== DEFAULT_VIEW) {
        newParams.set('view', view);
      } else {
        newParams.delete('view');
      }
      newParams.set('per_page', String(SEARCH_RESULTS_PER_PAGE));
    }

    if (perPage !== undefined) {
      newParams.set('per_page', String(SEARCH_RESULTS_PER_PAGE));
    } else if (newParams.has('per_page')) {
      newParams.set('per_page', String(SEARCH_RESULTS_PER_PAGE));
    }

    if (facets !== undefined) {
      // Preserve geo/bbox and year_range - they use distinct param structures
      Array.from(newParams.keys())
        .filter(
          (key) =>
            (key.startsWith('include_filters[') || key.startsWith('fq[')) &&
            !key.startsWith('include_filters[geo]') &&
            !key.startsWith('include_filters[year_range]')
        )
        .forEach((key) => newParams.delete(key));
      facets.forEach(({ field, value }) =>
        newParams.append(
          `include_filters[${field}][]`,
          normalizeFacetValueForUrl(field, value)
        )
      );
    }

    if (nextExcludeFacets !== undefined) {
      Array.from(newParams.keys())
        .filter((key) => key.startsWith('exclude_filters['))
        .forEach((key) => newParams.delete(key));
      nextExcludeFacets.forEach(({ field, value }) =>
        newParams.append(`exclude_filters[${field}][]`, value)
      );
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
      newParams.delete('page');
    }

    setSearchParams(newParams);
  };

  const handleViewChange = (newView: ViewMode) => {
    updateSearch({ view: newView, page: 1 });
  };

  const handlePageChange = (newPage: number) => updateSearch({ page: newPage });

  const handleRemoveFacet = (facetToRemove: FacetFilter) => {
    const updatedFacets = searchFacets.filter(
      (facet) =>
        !(
          facet.field === facetToRemove.field &&
          facet.value === facetToRemove.value
        )
    );
    updateSearch({ facets: updatedFacets });
  };

  const handleRemoveExclude = (facetToRemove: FacetFilter) => {
    const updated = (searchExcludeFacets || []).filter(
      (facet) =>
        !(
          facet.field === facetToRemove.field &&
          facet.value === facetToRemove.value
        )
    );
    updateSearch({ excludeFacets: updated });
  };

  const handleRemoveQuery = () => {
    updateSearch({ query: '' });
  };

  const handleRemoveAdvancedClause = (
    _clause: AdvancedClause,
    index: number
  ) => {
    const nextClauses = [...advancedQuery];
    nextClauses.splice(index, 1);
    updateSearch({ advancedQuery: nextClauses });
  };

  const handleClearAll = () => {
    const next = new URLSearchParams();
    next.set('q', '');
    setSearchParams(next);
  };

  const handleSortChange = (newSort: string) => {
    updateSearch({ sort: newSort });
  };

  const handleAdvancedApply = (clauses: typeof advancedQuery) => {
    // IMPORTANT: adv_q lives in the URL (source of truth for the loader).
    // We must update adv_q and close the builder in a single URL update,
    // otherwise we can accidentally clobber the just-written adv_q.
    const next = new URLSearchParams(searchParams);

    if (clauses.length > 0) {
      const serialized = clauses.map(({ op, field, q }) => ({
        op,
        f: field,
        q,
      }));
      next.set('adv_q', JSON.stringify(serialized));
    } else {
      next.delete('adv_q');
    }

    // Ensure a q param exists so searches run even with empty keyword queries.
    if (!next.has('q')) {
      next.set('q', query || '');
    }

    // Reset to page 1 when advanced clauses change
    next.delete('page');

    // Close the builder (gear icon / URL param is source of truth)
    next.delete('showAdvanced');

    setSearchParams(next);
  };

  const handleAdvancedReset = () => {
    updateSearch({ advancedQuery: [] });
  };

  // Extract spelling suggestions from meta
  const spellingSuggestions =
    activeSearchResults?.meta?.spellingSuggestions || [];

  useEffect(() => {
    if (activeIsLoading || !activeSearchResults) return;

    const metaQuery = activeSearchResults.meta?.query ?? '';
    const metaCurrentPage = activeSearchResults.meta?.currentPage ?? page;
    const metaPerPage = activeSearchResults.meta?.perPage ?? perPage;

    if (
      metaQuery !== normalizedQuery ||
      metaCurrentPage !== page ||
      metaPerPage !== perPage
    ) {
      return;
    }

    const pageResults = activeSearchResults.data || [];
    const trackedKey = [
      searchId,
      currentView,
      page,
      pageResults.map((result) => result.id).join(','),
    ].join(':');

    if (trackedAnalyticsKeysRef.current.has(trackedKey)) {
      return;
    }

    trackedAnalyticsKeysRef.current.add(trackedKey);

    scheduleAnalyticsBatch({
      searches: [
        {
          search_id: searchId,
          query: normalizedQuery,
          search_url: `/search${searchParams.toString() ? `?${searchParams.toString()}` : ''}`,
          view: currentView,
          page,
          per_page: perPage,
          sort,
          search_field: searchField,
          results_count: activeSearchResults.meta?.totalCount || 0,
          total_pages: activeSearchResults.meta?.totalPages || 0,
          zero_results: pageResults.length === 0,
          properties: {
            constraints: serializeSearchParams(searchParams),
            spelling_suggestions:
              activeSearchResults.meta?.spellingSuggestions || [],
          },
        },
      ],
      impressions: pageResults.map((result, index) => ({
        search_id: searchId,
        resource_id: result.id,
        rank: (page - 1) * perPage + index + 1,
        page,
        view: currentView,
      })),
    });
  }, [
    currentView,
    activeIsLoading,
    page,
    perPage,
    normalizedQuery,
    searchField,
    searchId,
    searchParams,
    activeSearchResults,
    sort,
  ]);

  // Type guard to check if suggestion is a SpellingSuggestion object
  const isSpellingSuggestion = (
    suggestion: unknown
  ): suggestion is { text: string; highlighted: string; score: number } => {
    return suggestion && typeof suggestion === 'object' && 'text' in suggestion;
  };

  return (
    <div className="min-h-screen flex flex-col">
      <Seo
        title={query ? `Search: ${query}` : 'Search Results'}
        description="Search existing resources in the Big Ten Academic Alliance Geoportal."
      />
      <Header />
      <main className="flex-1 bg-gray-50 pb-8">
        <h1 className="sr-only">
          {query ? `Search results for ${query}` : 'Search'}
        </h1>
        <div className="w-full px-4 sm:px-6 lg:px-8 pt-2">
          {/* Spelling Suggestions */}
          {spellingSuggestions.length > 0 && (
            <div className="mb-4 p-4 bg-blue-50 rounded-lg">
              <p className="text-sm text-blue-700">
                Did you mean:{' '}
                {spellingSuggestions.map((suggestion, index) => {
                  const suggestionText = isSpellingSuggestion(suggestion)
                    ? suggestion.text
                    : suggestion;
                  return (
                    <React.Fragment key={suggestionText}>
                      {index > 0 && ', '}
                      <button
                        onClick={() => updateSearch({ query: suggestionText })}
                        className="font-medium underline hover:text-blue-900"
                      >
                        {suggestionText}
                      </button>
                    </React.Fragment>
                  );
                })}
                ?
              </p>
            </div>
          )}

          <SearchConstraints
            facets={searchFacets}
            excludeFacets={searchExcludeFacets}
            query={query}
            advancedClauses={advancedQuery}
            onRemoveFacet={handleRemoveFacet}
            onRemoveExclude={handleRemoveExclude}
            onRemoveAdvancedClause={handleRemoveAdvancedClause}
            onRemoveQuery={handleRemoveQuery}
            onClearAll={handleClearAll}
          />

          {showAdvancedParam && (
            <div className="mb-8">
              <AdvancedSearchBuilder
                clauses={advancedQuery}
                onApply={handleAdvancedApply}
                onCancel={() => {
                  const next = new URLSearchParams(searchParams);
                  next.delete('showAdvanced');
                  setSearchParams(next);
                }}
                onReset={handleAdvancedReset}
              />
            </div>
          )}

          {/* Two columns: left = Filter Results (heading + map + facets), right = single column with "Showing results" + list/gallery/map */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-x-8 gap-y-2 mt-4">
            {isFilterDrawerOpen && (
              <button
                type="button"
                className="fixed inset-0 z-40 bg-slate-900/40 lg:hidden"
                aria-label="Close filters"
                onClick={() => setIsFilterDrawerOpen(false)}
              />
            )}

            {/* Left column: filters */}
            <aside
              id="search-filters-panel"
              aria-label="Filter results"
              className={`${
                isFilterDrawerOpen ? 'block' : 'hidden'
              } fixed inset-y-0 left-0 z-50 w-[min(92vw,24rem)] overflow-y-auto bg-white px-4 py-4 shadow-xl lg:sticky lg:inset-auto lg:top-40 lg:z-10 lg:col-span-3 lg:block lg:w-auto lg:self-start lg:overflow-visible lg:bg-transparent lg:p-0 lg:shadow-none`}
            >
              <div className="mb-4 flex items-center justify-between lg:hidden">
                <h2 className="text-base font-semibold text-gray-900">
                  Filter Results
                </h2>
                <button
                  type="button"
                  className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-700"
                  aria-label="Close filters"
                  onClick={() => setIsFilterDrawerOpen(false)}
                >
                  <X className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
              <h2 className="sr-only text-lg font-semibold text-gray-900">
                Filter Results
              </h2>
              {shouldRenderFilterContent && (
                <>
                  <LocationFacetCollapsible
                    accordion={accordion}
                    setAccordion={setAccordion}
                    showMap={shouldShowLocationFacetMap}
                  />
                  {activeSearchResults?.included ? (
                    <FacetList
                      facets={activeSearchResults.included.filter(
                        (item) =>
                          item.type === 'facet' || item.type === 'timeline'
                      )}
                      accordion={accordion}
                      setAccordion={setAccordion}
                    />
                  ) : (
                    <div className="text-gray-500">Loading facets...</div>
                  )}
                </>
              )}
            </aside>

            {/* Right column: "Showing results" header + results list / gallery / map view */}
            <div className="lg:col-span-9 flex flex-col pt-0 mt-0">
              {!hasNoSearchResults && (
                <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  {error ? (
                    <h2 className="text-lg text-gray-600">Results</h2>
                  ) : activeIsLoading || shouldShowSearchingPlaceholder ? (
                    <h2 className="text-lg text-gray-600">Searching…</h2>
                  ) : (
                    <h2 className="text-lg text-gray-600">
                      Showing results{' '}
                      {(() => {
                        const start = Math.min(
                          (page - 1) * perPage + 1,
                          searchTotalResults
                        );
                        const end = Math.min(
                          page * perPage,
                          searchTotalResults
                        );
                        return `${formatCount(start)}-${formatCount(end)}`;
                      })()}{' '}
                      of {formatCount(searchTotalResults)}
                    </h2>
                  )}
                  {!error && (
                    <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                      <button
                        type="button"
                        className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-900 shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-700 lg:hidden"
                        aria-controls="search-filters-panel"
                        aria-expanded={isFilterDrawerOpen}
                        onClick={() => {
                          setHasOpenedFilterDrawer(true);
                          setIsFilterDrawerOpen(true);
                        }}
                      >
                        <SlidersHorizontal
                          className="h-4 w-4"
                          aria-hidden="true"
                        />
                        <span>Filters</span>
                        {activeFilterCount > 0 && (
                          <span className="inline-flex min-w-5 items-center justify-center rounded-full bg-blue-700 px-1.5 text-xs font-semibold text-white">
                            {activeFilterCount}
                          </span>
                        )}
                      </button>
                      <ViewToggle
                        currentView={currentView}
                        onViewChange={handleViewChange}
                      />
                      <SortControl
                        options={
                          activeSearchResults?.included
                            ?.filter((item) => item.type === 'sort')
                            .map((sortOption) => ({
                              id: sortOption.id,
                              label: sortOption.attributes.label,
                              url: sortOption.links?.self || '',
                            })) || []
                        }
                        currentSort={sort || 'relevance'}
                        onSortChange={handleSortChange}
                      />
                    </div>
                  )}
                </div>
              )}
              {error ? (
                <ErrorMessage message={error} />
              ) : hasNoSearchResults ? (
                <NoResultsSearchHelp
                  query={normalizedQuery}
                  advancedSearchHref={advancedSearchHref}
                />
              ) : (
                <>
                  {currentView === 'list' && (
                    <SearchResults
                      results={activeSearchResults?.data || []}
                      isLoading={activeIsLoading}
                      totalResults={searchTotalResults}
                      currentPage={page}
                      perPage={perPage}
                      searchId={searchId}
                      searchView={currentView}
                    />
                  )}

                  {currentView === 'gallery' && (
                    <GalleryView
                      results={activeSearchResults?.data || []}
                      isLoading={activeIsLoading}
                      totalResults={searchTotalResults}
                      currentPage={page}
                      perPage={perPage}
                      searchId={searchId}
                    />
                  )}

                  {currentView === 'map' && (
                    <div className="grid grid-cols-1 md:grid-cols-9 gap-4 relative mt-0 pt-0">
                      {/* Middle Column: Brief Results */}
                      <div className="md:col-span-4 pr-2">
                        <SearchResults
                          results={activeSearchResults?.data || []}
                          isLoading={activeIsLoading}
                          totalResults={searchTotalResults}
                          currentPage={page}
                          perPage={perPage}
                          variant="compact"
                          searchId={searchId}
                          searchView={currentView}
                        />
                        {/* Pagination for map view (inside scrollable column) */}
                        {!activeIsLoading && totalPages > 1 && (
                          <div className="mt-4">
                            <Pagination
                              currentPage={page}
                              totalPages={totalPages}
                              onPageChange={handlePageChange}
                            />
                          </div>
                        )}
                      </div>

                      {/* Right Column: Map */}
                      <div className="md:col-span-5 min-w-0 sticky top-40 h-[calc(100vh-10rem)]">
                        <MapResultView
                          results={activeSearchResults?.data || []}
                          highlightedResourceId={hoveredResourceId}
                          highlightedGeometry={hoveredGeometry}
                          resultStartIndex={(page - 1) * perPage + 1}
                        />
                      </div>
                    </div>
                  )}

                  {/* Pagination for List and Grid views (bottom of page) */}
                  {!activeIsLoading &&
                    totalPages > 1 &&
                    (currentView === 'list' || currentView === 'gallery') && (
                      <Pagination
                        currentPage={page}
                        totalPages={totalPages}
                        onPageChange={handlePageChange}
                      />
                    )}
                </>
              )}
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}

export function SearchPage({
  searchResults,
  isLoading,
  clientSearchEnabled,
}: SearchPageProps) {
  return (
    <MapProvider>
      <SearchContent
        searchResults={searchResults ?? null}
        isLoading={isLoading ?? false}
        clientSearchEnabled={clientSearchEnabled}
      />
    </MapProvider>
  );
}

import React from 'react';
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
// import { MapView } from '../components/search/MapView';
import { MapProvider, useMap } from '../context/MapContext';
import { SortControl } from '../components/search/SortControl';
import { ViewToggle, type ViewMode } from '../components/search/ViewToggle';
import { GalleryView } from '../components/search/GalleryView';
import { MapResultView } from '../components/search/MapResultView';
import { AdvancedSearchBuilder } from '../components/search/AdvancedSearchBuilder';
import { GeospatialFilterMap } from '../components/search/GeospatialFilterMap';
import {
  parseSearchParams,
  normalizeFacetValueForUrl,
} from '../utils/searchParams';
import { formatCount } from '../utils/formatNumber';
import type { JsonApiResponse, GeoDocument } from '../types/api';
import { useState, useEffect, useRef } from 'react';

const GALLERY_STATE_STORAGE_KEY = 'b1g_gallery_state';

const isQuotaExceededError = (error: unknown): boolean => {
  if (error instanceof DOMException) {
    return (
      error.name === 'QuotaExceededError' ||
      error.name === 'NS_ERROR_DOM_QUOTA_REACHED'
    );
  }
  return false;
};

const persistGalleryState = (state: {
  context: string;
  results: GeoDocument[];
  startPage: number;
}) => {
  try {
    sessionStorage.setItem(GALLERY_STATE_STORAGE_KEY, JSON.stringify(state));
  } catch (error) {
    if (isQuotaExceededError(error)) {
      // Avoid crashing the page when gallery payload exceeds browser storage quota.
      try {
        sessionStorage.removeItem(GALLERY_STATE_STORAGE_KEY);
      } catch {
        // ignore cleanup errors
      }
      console.warn(
        'Gallery state cache exceeded session storage quota; skipping persistence.'
      );
      return;
    }
    throw error;
  }
};

type SearchPageProps = {
  // Loader-provided results (SSR/server-side).
  searchResults?: JsonApiResponse | null;
  // Navigation state from the route (client transitions).
  isLoading?: boolean;
};

// Create a separate component for the search content
function SearchContent({ searchResults, isLoading }: SearchPageProps) {
  const { hoveredResourceId, hoveredGeometry } = useMap();
  const [searchParams, setSearchParams] = useSearchParams();
  const showAdvancedParam = searchParams.get('showAdvanced') === 'true';

  // Ensure ?q= is present if no params are set to trigger default search
  useEffect(() => {
    if (Array.from(searchParams.keys()).length === 0) {
      setSearchParams({ q: '' }, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  const {
    query,
    page,
    facets: searchFacets,
    excludeFacets: searchExcludeFacets,
    advancedQuery,
  } = parseSearchParams(searchParams);
  const sort = searchParams.get('sort') || 'relevance';
  const currentView = (searchParams.get('view') as ViewMode) || 'list';

  const perPageParam = searchParams.get('per_page');
  const perPage =
    currentView === 'gallery'
      ? 20
      : perPageParam
        ? parseInt(perPageParam)
        : searchResults?.meta?.perPage || 10;
  const searchTotalResults = searchResults?.meta?.totalCount || 0;
  const totalPages = Math.ceil(searchTotalResults / perPage);

  // For now, treat API errors as “no results” and let ErrorMessage show when needed.
  const error = (searchResults as any)?.error
    ? String((searchResults as any).error)
    : null;

  // Infinite Scroll State for Gallery View
  // Initialize with server data to prevent hydration mismatch
  const [accumulatedResults, setAccumulatedResults] = useState<GeoDocument[]>(
    searchResults?.data || []
  );

  // Track the starting page of the accumulated results (for deep links)
  // Track the starting page of the accumulated results (for deep links)
  const [accumulatedStartPage, setAccumulatedStartPage] =
    useState<number>(page);

  // Helper to get stable context string (excluding page and per_page for gallery consistency)
  const getSearchContext = (params: URLSearchParams) => {
    const keys = Array.from(params.keys())
      .filter((k) => k !== 'page' && k !== 'per_page')
      .sort();
    return keys
      .map((k) => `${k}=${params.getAll(k).sort().join(',')}`)
      .join('&');
  };

  const currentContext = getSearchContext(searchParams);
  const prevContextRef = useRef(currentContext); // Initialize with current

  // Track if restoration has been attempted
  const [hasRestored, setHasRestored] = useState(false);

  // Restore state from session storage on mount (Client-side only)
  useEffect(() => {
    try {
      const cached = sessionStorage.getItem(GALLERY_STATE_STORAGE_KEY);
      if (cached) {
        const { context, results, startPage } = JSON.parse(cached);

        // Also check if view is gallery
        const isGallery = (searchParams.get('view') || 'list') === 'gallery';

        if (context === currentContext && isGallery) {
          setAccumulatedResults(results);
          if (startPage) setAccumulatedStartPage(startPage);
        }
      }
    } catch (e) {
      console.warn('Failed to restore gallery state:', e);
    } finally {
      setHasRestored(true);
    }
  }, []); // Run once on mount

  // Persist state to session storage
  useEffect(() => {
    // Only persist if we have finished checking for a restore (hasRestored is true)
    if (
      hasRestored &&
      currentView === 'gallery' &&
      accumulatedResults.length > 0
    ) {
      const state = {
        context: currentContext,
        results: accumulatedResults,
        startPage: accumulatedStartPage,
      };
      persistGalleryState(state);
    }
  }, [
    accumulatedResults,
    accumulatedStartPage,
    currentContext,
    currentView,
    hasRestored,
  ]);

  // Effect to manage accumulated results
  useEffect(() => {
    if (!hasRestored) return;

    const prevContext = prevContextRef.current;

    // If context changed (query, filters, view, sort) OR view is not gallery
    // We strictly compare the stable context string.
    if (currentContext !== prevContext || currentView !== 'gallery') {
      // Context changed: Reset everything
      setAccumulatedResults(searchResults?.data || []);
      setAccumulatedStartPage(page);
      // Clear cache for new context (optional, but good for cleanup)
      sessionStorage.removeItem(GALLERY_STATE_STORAGE_KEY);
    } else {
      // Context is SAME. Check page.
      if (page === 1) {
        // If page is 1, we USUALLY reset, but check if we have more cached data
        // If we have cached data covering page 1, we might want to keep it?
        // Actually, explicit page 1 navigation usually implies "Start Over".
        // BUT, if we just came back from ResourceView (via Back button), we might be at page 1.

        // HOWEVER, logic: If user hits Reload at Page 1, we fetch Page 1.
        // If accumulatedResults has 60 items (P1-P3), and we are at P1.
        // We probably want to keep the 60 items so scroll position is reliable?
        // But if user performs a NEW search that results in Page 1... context would change.

        // So: If Context is SAME, and Page is 1.
        // If we already have results starting at 1, and length > 20, keep them?
        if (
          accumulatedResults.length > (searchResults?.data?.length || 0) &&
          accumulatedStartPage === 1
        ) {
          // Do nothing, keep accumulated results
        } else {
          setAccumulatedResults(searchResults?.data || []);
          setAccumulatedStartPage(1);
        }
      } else {
        // Page > 1 and Same Context -> Append
        if (searchResults?.data && searchResults.data.length > 0) {
          setAccumulatedResults((prev) => {
            const existingIds = new Set(prev.map((r) => r.id));
            const newItems = (searchResults?.data || []).filter(
              (r) => !existingIds.has(r.id)
            );
            if (newItems.length === 0) return prev;
            return [...prev, ...newItems];
          });
          // Preserve accumulatedStartPage (it remains whatever it was: 1, or startPage of deep link)
        }
      }
    }

    prevContextRef.current = currentContext;
  }, [
    searchResults,
    currentContext,
    page,
    currentView,
    accumulatedResults.length,
    accumulatedStartPage,
    hasRestored,
  ]);

  const hasAnySearchCriteria =
    searchParams.has('q') ||
    searchParams.has('adv_q') ||
    Array.from(searchParams.keys()).some(
      (key) =>
        key.startsWith('include_filters[') ||
        key.startsWith('exclude_filters[') ||
        key.startsWith('fq[')
    );

  const shouldShowSearchingPlaceholder =
    !error && hasAnySearchCriteria && !searchResults && !isLoading;

  // Restore view preference whenever URL lacks a view param.
  // This keeps preferred layout sticky even when new searches navigate to /search?q=...
  useEffect(() => {
    if (searchParams.has('view')) return;

    const savedView = localStorage.getItem(
      'b1g_view_preference'
    ) as ViewMode | null;
    if (!savedView) return;

    const next = new URLSearchParams(searchParams);

    if (savedView === 'gallery' || savedView === 'map') {
      next.set('view', savedView);
      if (savedView === 'gallery') next.set('per_page', '20');
      else next.delete('per_page');
      setSearchParams(next, { replace: true });
      return;
    }

    // savedView === 'list' should behave as explicit default.
    if (next.has('per_page')) {
      next.delete('per_page');
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

      if (view !== 'list') {
        newParams.set('view', view);
        // Set per_page=20 for gallery view
        if (view === 'gallery') {
          newParams.set('per_page', '20');
        } else {
          // For map view, arguably we also want 20? But user specifically said "The 'Gallery' view...".
          // Let's stick to default for map unless requested.
          newParams.delete('per_page');
        }
      } else {
        newParams.delete('view');
        newParams.delete('per_page');
      }
    } else {
      // If updating other params but staying on gallery, ensure per_page=20 is preserved?
      // Actually URL params persist, so we don't need to re-set it unless we are blindly recreating/clearing params.
      // But updateSearch generally modifies existing searchParams (init'd from hook).
      // However, if we enter gallery via view change, we set it.
    }

    if (perPage !== undefined) {
      if (perPage !== 10) newParams.set('per_page', perPage.toString());
      else newParams.delete('per_page');
    }

    if (facets !== undefined) {
      Array.from(newParams.keys())
        .filter(
          (key) => key.startsWith('include_filters[') || key.startsWith('fq[')
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

    // Prevent scroll reset for infinite scroll in Gallery view
    const isGallery =
      view === 'gallery' || (!view && searchParams.get('view') === 'gallery');

    setSearchParams(newParams, {
      preventScrollReset: isGallery,
    });
  };

  const handleViewChange = (newView: ViewMode) => {
    updateSearch({ view: newView, page: 1 }); // Reset to page 1 to allow fresh infinite scroll start or clean switch
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
    const newParams = new URLSearchParams();
    // Clear all search params including geo filters
    setSearchParams(newParams);
    updateSearch({
      query: '',
      facets: [],
      excludeFacets: [],
      advancedQuery: [],
    });
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
  const spellingSuggestions = searchResults?.meta?.spellingSuggestions || [];

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
            {/* Left column: filters */}
            <div className="lg:col-span-3 lg:self-start space-y-4">
              <h2 className="sr-only text-lg font-semibold text-gray-900">
                Filter Results
              </h2>
              <GeospatialFilterMap />
              {searchResults?.included ? (
                <FacetList
                  facets={searchResults.included.filter(
                    (item) => item.type === 'facet' || item.type === 'timeline'
                  )}
                />
              ) : (
                <div className="text-gray-500">Loading facets...</div>
              )}
            </div>

            {/* Right column: "Showing results" header + results list / gallery / map view */}
            <div className="lg:col-span-9 flex flex-col pt-0 mt-0">
              <div className="mb-2 flex justify-between items-center">
                {error ? (
                  <h2 className="text-lg text-gray-600">Results</h2>
                ) : isLoading || shouldShowSearchingPlaceholder ? (
                  <h2 className="text-lg text-gray-600">Searching…</h2>
                ) : (
                  <h2 className="text-lg text-gray-600">
                    Showing results{' '}
                    {(() => {
                      let start, end;
                      if (
                        currentView === 'gallery' &&
                        accumulatedResults.length > 0
                      ) {
                        start = (accumulatedStartPage - 1) * perPage + 1;
                        end = start + accumulatedResults.length - 1;
                      } else {
                        start = Math.min(
                          (page - 1) * perPage + 1,
                          searchTotalResults
                        );
                        end = Math.min(page * perPage, searchTotalResults);
                      }
                      return `${formatCount(start)}-${formatCount(end)}`;
                    })()}{' '}
                    of {formatCount(searchTotalResults)}
                  </h2>
                )}
                {!error && (
                  <div className="flex items-center gap-4">
                    <ViewToggle
                      currentView={currentView}
                      onViewChange={handleViewChange}
                    />
                    <SortControl
                      options={
                        searchResults?.included
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
              {error ? (
                <ErrorMessage message={error} />
              ) : (
                <>
                  {currentView === 'list' && (
                    <SearchResults
                      results={searchResults?.data || []}
                      isLoading={isLoading}
                      totalResults={searchTotalResults}
                      currentPage={page}
                      perPage={perPage}
                    />
                  )}

                  {currentView === 'gallery' && (
                    <GalleryView
                      results={
                        accumulatedResults.length > 0
                          ? accumulatedResults
                          : searchResults?.data || []
                      }
                      isLoading={isLoading}
                      totalResults={searchTotalResults}
                      currentPage={page}
                      startPage={
                        accumulatedResults.length > 0
                          ? accumulatedStartPage
                          : page
                      }
                      perPage={perPage}
                      hasMore={page < totalPages}
                      onLoadMore={() => handlePageChange(page + 1)}
                    />
                  )}

                  {currentView === 'map' && (
                    <div className="grid grid-cols-1 md:grid-cols-9 gap-4 relative mt-0 pt-0">
                      {/* Middle Column: Brief Results */}
                      <div className="md:col-span-4 pr-2">
                        <SearchResults
                          results={searchResults?.data || []}
                          isLoading={isLoading}
                          totalResults={searchTotalResults}
                          currentPage={page}
                          perPage={perPage}
                          variant="compact"
                        />
                        {/* Pagination for map view (inside scrollable column) */}
                        {!isLoading && totalPages > 1 && (
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
                          results={searchResults?.data || []}
                          highlightedResourceId={hoveredResourceId}
                          highlightedGeometry={hoveredGeometry}
                          resultStartIndex={(page - 1) * perPage + 1}
                        />
                      </div>
                    </div>
                  )}

                  {/* Pagination for List view (bottom of page) */}
                  {!isLoading && totalPages > 1 && currentView === 'list' && (
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

export function SearchPage({ searchResults, isLoading }: SearchPageProps) {
  return (
    <MapProvider>
      <SearchContent
        searchResults={searchResults ?? null}
        isLoading={isLoading ?? false}
      />
    </MapProvider>
  );
}

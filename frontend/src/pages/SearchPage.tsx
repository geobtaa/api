import React from 'react';
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
import { MapProvider } from '../context/MapContext';
import { SortControl } from '../components/search/SortControl';
import { AdvancedSearchBuilder } from '../components/search/AdvancedSearchBuilder';
import { GeospatialFilterMap } from '../components/search/GeospatialFilterMap';
import { parseSearchParams } from '../utils/searchParams';
import type { JsonApiResponse } from '../types/api';

type SearchPageProps = {
  // Loader-provided results (SSR/server-side).
  searchResults?: JsonApiResponse | null;
  // Navigation state from the route (client transitions).
  isLoading?: boolean;
};

// Create a separate component for the search content
function SearchContent({ searchResults, isLoading }: SearchPageProps) {
  console.log('🔄 SearchContent rendering...');

  const [searchParams, setSearchParams] = useSearchParams();
  const showAdvancedParam = searchParams.get('showAdvanced') === 'true';

  const {
    query,
    page,
    facets: searchFacets,
    excludeFacets: searchExcludeFacets,
    advancedQuery,
  } = parseSearchParams(searchParams);
  const sort = searchParams.get('sort') || 'relevance';

  const perPage = searchResults?.meta?.perPage || 10;
  const searchTotalResults = searchResults?.meta?.totalCount || 0;
  const totalPages = Math.ceil(searchTotalResults / perPage);

  // For now, treat API errors as “no results” and let ErrorMessage show when needed.
  const error = (searchResults as any)?.error ? String((searchResults as any).error) : null;

  console.log('📊 SearchContent state:', {
    query,
    resultsCount: searchResults?.data?.length || 0,
    isLoading,
    error: !!error,
    page,
    totalResults: searchTotalResults,
    facetsCount: searchFacets.length,
    sort,
  });

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

    if (facets !== undefined) {
      Array.from(newParams.keys())
        .filter((key) => key.startsWith('include_filters[') || key.startsWith('fq['))
        .forEach((key) => newParams.delete(key));
      facets.forEach(({ field, value }) => newParams.append(`include_filters[${field}][]`, value));
    }

    if (nextExcludeFacets !== undefined) {
      Array.from(newParams.keys())
        .filter((key) => key.startsWith('exclude_filters['))
        .forEach((key) => newParams.delete(key));
      nextExcludeFacets.forEach(({ field, value }) =>
        newParams.append(`exclude_filters[${field}][]`, value),
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
      <Header />
      <main className="flex-1 bg-gray-50 pb-8">
        <div className="w-full px-4 sm:px-6 lg:px-8 pt-6">
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

          {/* Responsive grid layout */}
          <div className="mt-8 grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Facets - Collapsible on mobile */}
            <div className="lg:col-span-3">
              <div className="space-y-4">
                <GeospatialFilterMap />

                {searchResults?.included ? (
                  <FacetList
                    facets={searchResults.included.filter(
                      (item) => item.type === 'facet'
                    )}
                  />
                ) : (
                  <div className="text-gray-500">Loading facets...</div>
                )}
              </div>
            </div>

            {/* Results - Full width on mobile */}
            <div className="lg:col-span-9">
              {error ? (
                <ErrorMessage message={error} />
              ) : (
                <>
                  <div className="mb-6 flex justify-between items-center">
                    {isLoading || shouldShowSearchingPlaceholder ? (
                      <h2 className="text-lg text-gray-600">Searching…</h2>
                    ) : (
                      <h2 className="text-lg text-gray-600">
                        Showing results{' '}
                        {Math.min((page - 1) * perPage + 1, searchTotalResults)}-
                        {Math.min(page * perPage, searchTotalResults)} of{' '}
                        {searchTotalResults}
                      </h2>
                    )}
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

                  <SearchResults
                    results={searchResults?.data || []}
                    isLoading={isLoading}
                    totalResults={searchTotalResults}
                    currentPage={page}
                  />

                  {!isLoading && totalPages > 1 && (
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
      <SearchContent searchResults={searchResults ?? null} isLoading={isLoading ?? false} />
    </MapProvider>
  );
}

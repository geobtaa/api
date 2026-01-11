import React, { useState, useEffect } from 'react';
import { Header } from '../components/layout/Header';
import { Footer } from '../components/layout/Footer';
import { SearchResults } from '../components/SearchResults';
import { useBookmarks } from '../context/BookmarkContext';
import { fetchBookmarkedResources } from '../services/api';
import { useApi } from '../context/ApiContext';
import type { JsonApiResponse } from '../types/api';
import { MapProvider } from '../context/MapContext';
import { FacetList } from '../components/FacetList';
import { MapView } from '../components/search/MapView';
import { SortControl } from '../components/search/SortControl';
import { CONFIGURED_FACETS } from '../constants/facets';
import { formatCount } from '../utils/formatNumber';

export function BookmarksPage() {
  const { bookmarks } = useBookmarks();
  const [results, setResults] = useState<JsonApiResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { setLastApiUrl } = useApi();
  const [sort, setSort] = useState('relevance');

  useEffect(() => {
    const fetchResults = async () => {
      setIsLoading(true);
      try {
        const response = await fetchBookmarkedResources(
          bookmarks,
          setLastApiUrl
        );
        setResults(response);
      } catch (error) {
        console.error('Error fetching bookmarks:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchResults();
  }, [bookmarks, setLastApiUrl]);

  const filteredFacets = results?.included
    ? results.included.filter(
        (
          item
        ): item is {
          type: 'facet';
          id: string;
          attributes: Record<string, unknown>;
        } =>
          item.type === 'facet' &&
          CONFIGURED_FACETS.includes(
            item.id as (typeof CONFIGURED_FACETS)[number]
          )
      )
    : [];

  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <MapProvider>
        <main className="flex-1 bg-gray-50">
          <div className="max-w-[1920px] mx-auto px-4 sm:px-6 lg:px-8">
            {/* Title and Sort - Stack on mobile */}
            <div className="py-6">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <h1 className="text-2xl font-bold text-gray-900">
                  Bookmarked Resources ({formatCount(bookmarks.length)})
                </h1>
                {results?.included?.filter((item) => item.type === 'sort')
                  .length > 0 && (
                  <SortControl
                    options={results.included
                      .filter((item) => item.type === 'sort')
                      .map((sortOption) => ({
                        id: sortOption.id,
                        label: sortOption.attributes.label,
                        url: sortOption.links?.self || '',
                      }))}
                    currentSort={sort}
                    onSortChange={setSort}
                  />
                )}
              </div>
            </div>

            {/* Main grid layout */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* Facets Sidebar - Collapsible on mobile */}
              <aside className="lg:col-span-2">
                <details className="lg:hidden mb-4">
                  <summary className="text-lg font-semibold cursor-pointer py-2">
                    Filter Results
                  </summary>
                  {results?.included?.filter((item) => item.type === 'facet')
                    .length > 0 && <FacetList facets={filteredFacets} />}
                </details>
                <div className="hidden lg:block">
                  <div className="sticky top-16">
                    <div className="p-6 overflow-y-auto max-h-[calc(100vh-4rem)]">
                      <h2 className="text-lg font-semibold text-gray-900 mb-4">
                        Filter Results
                      </h2>
                      {results?.included?.filter(
                        (item) => item.type === 'facet'
                      ).length > 0 && <FacetList facets={filteredFacets} />}
                    </div>
                  </div>
                </div>
              </aside>

              {/* Results Column - Full width on mobile */}
              <div className="lg:col-span-6">
                <div className="space-y-6">
                  <SearchResults
                    results={results?.data || []}
                    isLoading={isLoading}
                    totalResults={results?.meta.totalCount || 0}
                    currentPage={1}
                  />
                </div>
              </div>

              {/* Map Column - Hidden by default on mobile */}
              <div className="hidden lg:block lg:col-span-4">
                <div className="sticky top-16 h-[calc(100vh-4rem)]">
                  <MapView results={results?.data || []} />
                </div>
              </div>
            </div>
          </div>
        </main>
      </MapProvider>
      <Footer />
    </div>
  );
}

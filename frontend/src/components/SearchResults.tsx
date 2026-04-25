import { useState } from 'react';
import { Link, useLocation } from 'react-router';
import type { GeoDocument } from '../types/api';
import { BookOpen } from 'lucide-react';
import { useDebug } from '../context/DebugContext';
import { useMap } from '../context/MapContext';
import { BookmarkButton } from './BookmarkButton';
import { useBookmarks } from '../context/BookmarkContext';
import { getResourceIcon } from '../utils/resourceIcons';
import { getHoverGeometryForResult } from '../utils/geometryUtils';
import { getResultPrimaryImageUrl } from '../utils/resourceAssets';
import { fetchResourceDetails } from '../services/api';
import { scheduleAnalyticsBatch } from '../services/analytics';
import { StaticResultMap } from './search/StaticResultMap';
import { ResultCardPill } from './search/ResultCardPill';

interface SearchResultsProps {
  results: GeoDocument[];
  isLoading: boolean;
  totalResults: number;
  currentPage: number;
  perPage?: number;
  variant?: 'default' | 'compact';
  searchId?: string;
  searchView?: 'list' | 'gallery' | 'map';
}

export function SearchResults({
  results,
  isLoading,
  totalResults,
  currentPage,
  perPage = 10,
  variant = 'default',
  searchId,
  searchView = 'list',
}: SearchResultsProps) {
  const { showDetails } = useDebug();
  const location = useLocation();
  const { setHoveredGeometry, setHoveredResourceId, setGeometryIfHovering } =
    useMap();
  const { isBookmarked } = useBookmarks();
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

  const isCompact = variant === 'compact';

  // Calculate absolute index in full result set (1-based)
  const getAbsoluteIndex = (relativeIndex: number) => {
    return (currentPage - 1) * perPage + relativeIndex + 1;
  };

  const trackResultClick = (
    resourceId: string,
    title: string,
    relativeIndex: number
  ) => {
    scheduleAnalyticsBatch({
      events: [
        {
          event_type: 'result_click',
          search_id: searchId,
          resource_id: resourceId,
          rank: getAbsoluteIndex(relativeIndex),
          page: currentPage,
          view: searchView,
          label: title,
          source_component: 'SearchResults',
          properties: {
            search_url: location.pathname + location.search,
            total_results: totalResults,
          },
        },
      ],
    });
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div>
        <p className="text-gray-500">No results found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {results.map((result, index) => {
        const ogm = result?.attributes?.ogm;
        const title = ogm?.dct_title_s ?? '(Untitled)';
        const resourceClass = ogm?.gbl_resourceClass_sm?.[0];

        const hoverGeometry = getHoverGeometryForResult(result);
        return (
          <article
            key={result.id}
            className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow relative group"
            data-geom={hoverGeometry ?? ''}
            onMouseEnter={() => {
              setHoveredResourceId?.(result.id);
              if (hoverGeometry) {
                setHoveredGeometry(hoverGeometry);
              } else {
                setHoveredGeometry(null);
                // Fallback: search result may lack meta.ui.viewer.geometry; fetch full resource
                fetchResourceDetails(result.id)
                  .then((full) => {
                    const geom = getHoverGeometryForResult(full);
                    if (geom) setGeometryIfHovering(result.id, geom);
                  })
                  .catch(() => {});
              }
            }}
            onMouseLeave={() => {
              setHoveredGeometry(null);
              setHoveredResourceId?.(null);
            }}
          >
            <div className="flex">
              {/* Thumbnail */}
              <div
                className={`${isCompact ? 'w-24' : 'w-48'} flex-shrink-0 relative group/thumb`}
              >
                {(() => {
                  const primaryImageUrl = getResultPrimaryImageUrl(
                    result,
                    'list'
                  );
                  const hasThumbnail = !imageErrors.has(result.id);

                  return hasThumbnail ? (
                    <div
                      className={`${isCompact ? 'h-24 w-24' : 'h-48 w-48'} rounded-l-lg`}
                    >
                      <img
                        src={primaryImageUrl}
                        alt=""
                        loading={index < 2 ? 'eager' : 'lazy'}
                        decoding="async"
                        fetchPriority={index < 2 ? 'high' : 'low'}
                        className={`${isCompact ? 'h-24 w-24' : 'h-48 w-48'} object-cover rounded-l-lg`}
                        onError={(e) => {
                          setImageErrors((prev) =>
                            new Set(prev).add(result.id)
                          );
                        }}
                      />
                    </div>
                  ) : (
                    <div
                      className={`${isCompact ? 'h-24 w-24' : 'h-48 w-48'} flex items-center justify-center bg-gray-50 rounded-l-lg`}
                    >
                      {getResourceIcon(resourceClass)}
                    </div>
                  );
                })()}

                {/* Bookmark Button - Absolute Top Left on Image */}
                <div
                  className={`absolute top-1 left-1 z-20 transition-opacity duration-200 ${
                    isBookmarked(result.id)
                      ? 'opacity-100'
                      : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100'
                  }`}
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="bg-white rounded-full shadow-sm hover:shadow-md">
                    <BookmarkButton itemId={result.id} />
                  </div>
                </div>
              </div>

              {/* Result Number (Index) - Screen Reader Only */}
              <div className="sr-only">Result {getAbsoluteIndex(index)}</div>

              {/* Content */}
              {/* Content */}
              <div
                className={`flex-1 flex flex-col ${isCompact ? 'p-3' : 'p-6'}`}
              >
                {showDetails && (
                  <pre className="overflow-auto text-xs">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                )}

                <div className="flex items-start gap-2 mb-2 pr-8">
                  <span
                    className={`flex-shrink-0 font-semibold text-slate-600 dark:text-slate-400 ${isCompact ? 'text-sm' : 'text-xl'}`}
                    aria-hidden
                  >
                    {getAbsoluteIndex(index)}.
                  </span>
                  <Link
                    to={`/resources/${result.id}`}
                    onClick={() =>
                      trackResultClick(
                        result.id,
                        typeof title === 'string' ? title : String(title),
                        index
                      )
                    }
                    state={{
                      searchResults: results,
                      currentIndex: index, // Local index
                      absoluteIndex: getAbsoluteIndex(index) - 1, // Absolute index (0-based)
                      totalResults: totalResults,
                      searchUrl: location.pathname + location.search,
                      currentPage: currentPage,
                      perPage: perPage,
                      searchId: searchId,
                      view: searchView,
                    }}
                    className="flex-1"
                  >
                    <h2
                      className={`${isCompact ? 'text-sm line-clamp-2' : 'text-xl line-clamp-2'} font-semibold text-blue-600 hover:text-blue-800`}
                    >
                      {typeof title === 'string' ? title : String(title)}
                    </h2>
                  </Link>
                </div>

                {/* Year and resource type inline before description - Hide in compact mode */}
                {!isCompact && (
                  <p className="text-gray-600 mb-4 line-clamp-2">
                    <span className="text-sm font-medium flex-shrink-0">
                      <ResultCardPill
                        indexYear={ogm?.gbl_indexYear_im?.[0]}
                        resourceClass={resourceClass}
                        provider={ogm?.schema_provider_s}
                      />
                    </span>
                    {ogm?.dct_description_sm &&
                    Array.isArray(ogm.dct_description_sm) &&
                    ogm.dct_description_sm.length > 0 ? (
                      <span className="ml-1">
                        {ogm.dct_description_sm[0] &&
                          (typeof ogm.dct_description_sm[0] === 'string'
                            ? ogm.dct_description_sm[0]
                            : String(ogm.dct_description_sm[0]))}
                      </span>
                    ) : null}
                  </p>
                )}

                {/* Subject and Theme tags */}
                {isCompact ? (
                  <div className="mt-auto pt-2">
                    <ResultCardPill
                      indexYear={ogm?.gbl_indexYear_im?.[0]}
                      resourceClass={resourceClass}
                      provider={ogm?.schema_provider_s}
                    />
                  </div>
                ) : (
                  <div className="flex flex-col gap-4 flex-1">
                    {(() => {
                      // Get subjects from dct_subjects_sm or dct_subject_sm
                      const subjects =
                        (ogm?.dct_subjects_sm &&
                        Array.isArray(ogm.dct_subjects_sm) &&
                        ogm.dct_subjects_sm.length > 0
                          ? ogm.dct_subjects_sm
                          : null) ||
                        (ogm?.dct_subject_sm &&
                        Array.isArray(ogm.dct_subject_sm) &&
                        ogm.dct_subject_sm.length > 0
                          ? ogm.dct_subject_sm
                          : null);

                      // Get themes from dcat_theme_sm
                      const themes =
                        ogm?.dcat_theme_sm &&
                        Array.isArray(ogm.dcat_theme_sm) &&
                        ogm.dcat_theme_sm.length > 0
                          ? ogm.dcat_theme_sm
                          : null;

                      // Helper to create search URL for a tag
                      const createTagSearchUrl = (
                        field: string,
                        value: string | number
                      ) => {
                        const params = new URLSearchParams();
                        params.append(
                          `include_filters[${field}][]`,
                          value.toString()
                        );
                        return `/search?${params.toString()}`;
                      };

                      // Determine which field name to use for subjects
                      const subjectField = ogm?.dct_subjects_sm
                        ? 'dct_subjects_sm'
                        : 'dct_subject_sm';

                      return (subjects && subjects.length > 0) ||
                        (themes && themes.length > 0) ? (
                        <div className="flex flex-wrap gap-2">
                          {subjects?.map((subject, index) => {
                            const subjectValue =
                              typeof subject === 'string'
                                ? subject
                                : String(subject);
                            return (
                              <Link
                                key={`subject-${index}`}
                                to={createTagSearchUrl(
                                  subjectField,
                                  subjectValue
                                )}
                                className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors"
                                onClick={(e) => {
                                  // Prevent navigation if clicking on the result link
                                  e.stopPropagation();
                                }}
                              >
                                {subjectValue}
                              </Link>
                            );
                          })}
                          {themes?.map((theme, index) => {
                            const themeValue =
                              typeof theme === 'string' ? theme : String(theme);
                            return (
                              <Link
                                key={`theme-${index}`}
                                to={createTagSearchUrl(
                                  'dcat_theme_sm',
                                  themeValue
                                )}
                                className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800 hover:bg-purple-200 transition-colors"
                                onClick={(e) => {
                                  // Prevent navigation if clicking on the result link
                                  e.stopPropagation();
                                }}
                              >
                                {themeValue}
                              </Link>
                            );
                          })}
                        </div>
                      ) : null;
                    })()}

                    {/* Metadata Row: Publisher only (year and resource class are inline with description) */}
                    {ogm?.dc_publisher_sm &&
                      Array.isArray(ogm.dc_publisher_sm) &&
                      ogm.dc_publisher_sm.length > 0 && (
                        <div className="flex items-center text-sm text-gray-500 border-t border-gray-100 pt-3 mt-auto">
                          <div className="flex items-center gap-1">
                            <BookOpen size={16} />
                            <span>
                              {ogm.dc_publisher_sm
                                .map((item) =>
                                  typeof item === 'string' ? item : String(item)
                                )
                                .join(', ')}
                            </span>
                          </div>
                        </div>
                      )}
                  </div>
                )}
              </div>

              {/* Static Map - Hide in compact mode */}
              {!isCompact && (
                <div className="w-48 flex-shrink-0">
                  <StaticResultMap result={result} />
                </div>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}

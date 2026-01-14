import { useState } from 'react';
import { Link, useLocation } from 'react-router';
import type { GeoDocument } from '../types/api';
import { BookOpen } from 'lucide-react';
import { useDebug } from '../context/DebugContext';
import { useMap } from '../context/MapContext';
import { BookmarkButton } from './BookmarkButton';
import { getResourceIcon } from '../utils/resourceIcons';
import { StaticResultMap } from './search/StaticResultMap';

interface SearchResultsProps {
  results: GeoDocument[];
  isLoading: boolean;
  totalResults: number;
  currentPage: number;
}

export function SearchResults({
  results,
  isLoading,
  totalResults,
  currentPage,
}: SearchResultsProps) {
  const { showDetails } = useDebug();
  const location = useLocation();
  const { setHoveredGeometry } = useMap();
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

  const toSsrThumbnailUrl = (url: string): string => {
    // If backend gives us an API URL, route through SSR so requests use the server-held API key.
    // Example: https://host/api/v1/thumbnails/<hash>  ->  /thumbnails/<hash>
    //          /api/v1/thumbnails/placeholder        ->  /thumbnails/placeholder
    if (!url || typeof url !== 'string') {
      console.warn('toSsrThumbnailUrl: Invalid URL', url);
      return url;
    }

    try {
      // Handle absolute URLs (with protocol)
      if (url.startsWith('http://') || url.startsWith('https://')) {
        const u = new URL(url);
        if (u.pathname.startsWith('/api/v1/thumbnails/')) {
          const transformed = u.pathname.replace('/api/v1/thumbnails/', '/thumbnails/') + u.search;
          console.log('toSsrThumbnailUrl: Transformed absolute URL', { original: url, transformed });
          return transformed;
        }
        console.log('toSsrThumbnailUrl: Absolute URL but not a thumbnail path', url);
        return url;
      }

      // Handle relative URLs
      if (url.startsWith('/api/v1/thumbnails/')) {
        const transformed = url.replace('/api/v1/thumbnails/', '/thumbnails/');
        console.log('toSsrThumbnailUrl: Transformed relative URL', { original: url, transformed });
        return transformed;
      }

      // Try parsing as URL with base (for relative URLs that might need a base)
      const base = typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
      const u = new URL(url, base);
      if (u.pathname.startsWith('/api/v1/thumbnails/')) {
        const transformed = u.pathname.replace('/api/v1/thumbnails/', '/thumbnails/') + u.search;
        console.log('toSsrThumbnailUrl: Transformed URL with base', { original: url, transformed });
        return transformed;
      }

      return url;
    } catch (error) {
      console.warn('toSsrThumbnailUrl: Error parsing URL', { url, error });
      // Fallback: simple string replacement
      if (url.includes('/api/v1/thumbnails/')) {
        return url.replace('/api/v1/thumbnails/', '/thumbnails/');
      }
      return url;
    }
  };

  // Calculate absolute index in full result set
  const getAbsoluteIndex = (relativeIndex: number) => {
    return (currentPage - 1) * 10 + relativeIndex + 1;
  };

  // Add debug logging
  console.log('SearchResults props:', {
    resultCount: results.length,
    firstResult: results[0],
    thumbnailUrls: results.map((r) => ({
      id: r.id,
      thumbnail: r.meta?.ui?.thumbnail_url,
    })),
  });

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

        // Add detailed debugging to inspect the actual structure
        console.log('Raw result object:', {
          id: result.id,
          type: result.type,
          attributes: result.attributes,
          thumbnail: result.meta?.ui?.thumbnail_url,
          // Log the full object to see its structure
          fullResult: result,
        });

        // Deep inspection of meta structure
        console.log('Deep meta inspection:', {
          hasMeta: !!result.meta,
          metaKeys: result.meta ? Object.keys(result.meta) : [],
          hasMetaUi: !!result.meta?.ui,
          metaUiKeys: result.meta?.ui ? Object.keys(result.meta.ui) : [],
          thumbnailUrlDirect: result.meta?.ui?.thumbnail_url,
          thumbnailUrlBracket: result.meta?.ui?.['thumbnail_url'],
          metaUiStringified: result.meta?.ui ? JSON.stringify(result.meta.ui) : 'no ui',
          fullMetaStringified: result.meta ? JSON.stringify(result.meta) : 'no meta',
        });

        // Add detailed debug logging for thumbnails
        console.log('Full result object:', result);
        console.log('Result thumbnail debug:', {
          id: result.id,
          title,
          thumbnailUrl: result.meta?.ui?.thumbnail_url,
          resourceClass,
        });

        // Debug individual result
        console.log(`Rendering result ${result.id}:`, {
          title,
          thumbnail: result.meta?.ui?.thumbnail_url,
        });

        return (
          <article
            key={result.id}
            className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow relative"
            data-geom={
              result.meta?.ui?.viewer?.geometry
                ? JSON.stringify(result.meta.ui.viewer.geometry)
                : ''
            }
            onMouseEnter={() =>
              setHoveredGeometry(
                result.meta?.ui?.viewer?.geometry
                  ? JSON.stringify(result.meta.ui.viewer.geometry)
                  : null
              )
            }
            onMouseLeave={() => setHoveredGeometry(null)}
          >
            <div className="flex">
              {/* Thumbnail */}
              <div className="w-48 flex-shrink-0">
                {(() => {
                  // Try multiple ways to access thumbnail_url
                  const metaUi = result.meta?.ui;
                  const thumbnailUrl = 
                    metaUi?.thumbnail_url || 
                    metaUi?.['thumbnail_url'] ||
                    (metaUi && 'thumbnail_url' in metaUi ? (metaUi as any).thumbnail_url : undefined);

                  const hasThumbnail = 
                    thumbnailUrl &&
                    typeof thumbnailUrl === 'string' &&
                    thumbnailUrl.trim() !== '' &&
                    !imageErrors.has(result.id);

                  // Debug logging for thumbnail rendering decision
                  if (!hasThumbnail) {
                    console.log(`Thumbnail check for ${result.id}:`, {
                      hasMeta: !!result.meta,
                      hasMetaUi: !!result.meta?.ui,
                      thumbnailUrl: thumbnailUrl,
                      thumbnailUrlType: typeof thumbnailUrl,
                      thumbnailUrlTrimmed: typeof thumbnailUrl === 'string' ? thumbnailUrl.trim() : 'N/A',
                      isInImageErrors: imageErrors.has(result.id),
                      metaUiKeys: metaUi ? Object.keys(metaUi) : [],
                      metaUiHasOwnProperty: metaUi ? metaUi.hasOwnProperty('thumbnail_url') : false,
                      metaUiIn: metaUi ? 'thumbnail_url' in metaUi : false,
                      metaUiStringified: metaUi ? JSON.stringify(metaUi) : 'no ui',
                    });
                  }

                  return hasThumbnail ? (
                    <div className="h-48 w-48 rounded-l-lg">
                      <img
                        src={toSsrThumbnailUrl(thumbnailUrl)}
                        alt={`Thumbnail for ${title}`}
                        className="h-48 w-48 object-cover rounded-l-lg"
                        onError={(e) => {
                          console.error(
                            `Error loading thumbnail for ${result.id}:`,
                            {
                              originalUrl: thumbnailUrl,
                              transformedUrl: toSsrThumbnailUrl(thumbnailUrl),
                              error: e,
                              target: (e.target as HTMLImageElement)?.src,
                            }
                          );
                          setImageErrors((prev) => new Set(prev).add(result.id));
                        }}
                        onLoad={() => {
                          console.log(
                            `Successfully loaded thumbnail for ${result.id}:`,
                            {
                              originalUrl: thumbnailUrl,
                              transformedUrl: toSsrThumbnailUrl(thumbnailUrl),
                            }
                          );
                        }}
                      />
                    </div>
                  ) : (
                    <div className="h-48 w-48 flex items-center justify-center bg-gray-50 rounded-l-lg">
                      {getResourceIcon(resourceClass)}
                    </div>
                  );
                })()}
              </div>

              {/* Content */}
              <div className="flex-1 p-6">
                <div className="absolute -left-4 top-6 bg-gray-100 rounded-full w-8 h-8 flex items-center justify-center text-sm text-gray-500 font-medium">
                  {getAbsoluteIndex(index)}
                </div>

                {showDetails && (
                  <pre className="overflow-auto text-xs">
                    {JSON.stringify(result, null, 2)}
                  </pre>
                )}

                <div className="flex items-center gap-2 mb-2">
                  <BookmarkButton itemId={result.id} />
                  <Link
                    to={`/resources/${result.id}`}
                    state={{
                      searchResults: results,
                      currentIndex: getAbsoluteIndex(index) - 1,
                      totalResults: totalResults,
                      searchUrl: location.pathname + location.search,
                      currentPage: currentPage,
                    }}
                    className="flex-1"
                  >
                    <h2 className="text-xl font-semibold text-blue-600 hover:text-blue-800">
                      {typeof title === 'string' ? title : String(title)}
                    </h2>
                  </Link>
                </div>

                {/* Temporal information and Description (inline) */}
                {(ogm?.dct_temporal_sm &&
                  Array.isArray(ogm.dct_temporal_sm) &&
                  ogm.dct_temporal_sm.length > 0) ||
                (ogm?.dct_description_sm &&
                  Array.isArray(ogm.dct_description_sm) &&
                  ogm.dct_description_sm.length > 0) ? (
                  <p className="text-gray-600 mb-4 line-clamp-3">
                    {ogm?.dct_temporal_sm &&
                      Array.isArray(ogm.dct_temporal_sm) &&
                      ogm.dct_temporal_sm.length > 0 && (
                        <span className="text-gray-500 text-sm">
                          {ogm.dct_temporal_sm
                            .map((item) =>
                              typeof item === 'string' ? item : String(item)
                            )
                            .join(', ')}{' '}
                        </span>
                      )}
                    {ogm?.dct_description_sm &&
                      Array.isArray(ogm.dct_description_sm) &&
                      ogm.dct_description_sm.length > 0 &&
                      (typeof ogm.dct_description_sm[0] === 'string'
                        ? ogm.dct_description_sm[0]
                        : String(ogm.dct_description_sm[0]))}
                  </p>
                ) : null}

                {/* Subject and Theme tags */}
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
                    <div className="flex flex-wrap gap-2 mb-4">
                      {subjects?.map((subject, index) => {
                        const subjectValue =
                          typeof subject === 'string'
                            ? subject
                            : String(subject);
                        return (
                          <Link
                            key={`subject-${index}`}
                            to={createTagSearchUrl(subjectField, subjectValue)}
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
                            to={createTagSearchUrl('dcat_theme_sm', themeValue)}
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

                <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                  {ogm?.dc_publisher_sm &&
                    Array.isArray(ogm.dc_publisher_sm) &&
                    ogm.dc_publisher_sm.length > 0 && (
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
                    )}
                </div>
              </div>

              {/* Static Map */}
              <div className="w-48 flex-shrink-0">
                <StaticResultMap result={result} />
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}

import { useState } from 'react';
import { Link, useLocation } from 'react-router';
import type { GeoDocument } from '../types/api';
import { BookOpen } from 'lucide-react';
import { useDebug } from '../context/DebugContext';
import { useMap } from '../context/MapContext';
import { BookmarkButton } from './BookmarkButton';
import { useBookmarks } from '../context/BookmarkContext';
import { getResourceIcon } from '../utils/resourceIcons';
import { StaticResultMap } from './search/StaticResultMap';
import { ResultCardPill } from './search/ResultCardPill';

interface SearchResultsProps {
  results: GeoDocument[];
  isLoading: boolean;
  totalResults: number;
  currentPage: number;
  variant?: 'default' | 'compact';
}

export function SearchResults({
  results,
  isLoading,
  totalResults,
  currentPage,
  variant = 'default',
}: SearchResultsProps) {
  const { showDetails } = useDebug();
  const location = useLocation();
  const { setHoveredGeometry, setHoveredResourceId } = useMap();
  const { isBookmarked } = useBookmarks();
  const [imageErrors, setImageErrors] = useState<Set<string>>(new Set());

  const isCompact = variant === 'compact';

  // ... (keeping existing functions hidden for brevity in this replace call if possible, but replace_file_content needs contiguity. I'll target the top of component to add hook, and then separate calls for the loop content)

  const toSsrThumbnailUrl = (url: string): string => {
    // If backend gives us an API URL, route through SSR so requests use the server-held API key.
    // Example: https://host/api/v1/thumbnails/<hash>  ->  /thumbnails/<hash>
    //          /api/v1/thumbnails/placeholder        ->  /thumbnails/placeholder
    //          /api/v1/resources/{id}/thumbnail     ->  /resources/{id}/thumbnail
    if (!url || typeof url !== 'string') {
      console.warn('toSsrThumbnailUrl: Invalid URL', url);
      return url;
    }

    try {
      // Handle absolute URLs (with protocol)
      if (url.startsWith('http://') || url.startsWith('https://')) {
        const u = new URL(url);
        // Handle /api/v1/thumbnails/{hash} -> /thumbnails/{hash}
        if (u.pathname.startsWith('/api/v1/thumbnails/')) {
          const transformed =
            u.pathname.replace('/api/v1/thumbnails/', '/thumbnails/') +
            u.search;
          return transformed;
        }
        // Handle /api/v1/resources/{id}/thumbnail -> /resources/{id}/thumbnail
        if (u.pathname.match(/^\/api\/v1\/resources\/[^\/]+\/thumbnail$/)) {
          const transformed = u.pathname.replace('/api/v1', '') + u.search;
          return transformed;
        }
        return url;
      }

      // Handle relative URLs
      // /api/v1/thumbnails/{hash} -> /thumbnails/{hash}
      if (url.startsWith('/api/v1/thumbnails/')) {
        return url.replace('/api/v1/thumbnails/', '/thumbnails/');
      }

      // /api/v1/resources/{id}/thumbnail -> /resources/{id}/thumbnail
      const resourceThumbnailMatch = url.match(
        /^\/api\/v1(\/resources\/[^\/]+\/thumbnail)/
      );
      if (resourceThumbnailMatch) {
        return resourceThumbnailMatch[1];
      }

      // Try parsing as URL with base (for relative URLs that might need a base)
      const base =
        typeof window !== 'undefined'
          ? window.location.origin
          : 'http://localhost';
      const u = new URL(url, base);
      if (u.pathname.startsWith('/api/v1/thumbnails/')) {
        return (
          u.pathname.replace('/api/v1/thumbnails/', '/thumbnails/') + u.search
        );
      }
      if (u.pathname.match(/^\/api\/v1\/resources\/[^\/]+\/thumbnail$/)) {
        return u.pathname.replace('/api/v1', '') + u.search;
      }

      return url;
    } catch (error) {
      console.warn('toSsrThumbnailUrl: Error parsing URL', { url, error });
      // Fallback: simple string replacement
      if (url.includes('/api/v1/thumbnails/')) {
        return url.replace('/api/v1/thumbnails/', '/thumbnails/');
      }
      if (url.includes('/api/v1/resources/') && url.endsWith('/thumbnail')) {
        return url.replace('/api/v1', '');
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
        const metaUi = result.meta?.ui;
        const allMetaUiProps = metaUi ? Object.getOwnPropertyNames(metaUi) : [];
        const metaUiDescriptors = metaUi
          ? Object.getOwnPropertyDescriptors(metaUi)
          : {};

        console.log('Deep meta inspection:', {
          hasMeta: !!result.meta,
          metaKeys: result.meta ? Object.keys(result.meta) : [],
          hasMetaUi: !!metaUi,
          metaUiKeys: metaUi ? Object.keys(metaUi) : [],
          allMetaUiProps: allMetaUiProps,
          thumbnailUrlDirect: metaUi?.thumbnail_url,
          thumbnailUrlBracket: metaUi?.['thumbnail_url'],
          thumbnailUrlDescriptor: metaUiDescriptors['thumbnail_url'],
          metaUiStringified: metaUi ? JSON.stringify(metaUi) : 'no ui',
          fullMetaStringified: result.meta
            ? JSON.stringify(result.meta)
            : 'no meta',
          // Try to access via Object.getOwnPropertyDescriptor
          hasThumbnailProperty: metaUi && 'thumbnail_url' in metaUi,
          thumbnailUrlViaGetOwnProperty: metaUi
            ? Object.getOwnPropertyDescriptor(metaUi, 'thumbnail_url')?.value
            : undefined,
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
            className="bg-white rounded-lg shadow-md hover:shadow-lg transition-shadow relative group"
            data-geom={
              result.meta?.ui?.viewer?.geometry
                ? JSON.stringify(result.meta.ui.viewer.geometry)
                : ''
            }
            onMouseEnter={() => {
              setHoveredGeometry(
                result.meta?.ui?.viewer?.geometry
                  ? JSON.stringify(result.meta.ui.viewer.geometry)
                  : null
              );
              if (setHoveredResourceId) setHoveredResourceId(result.id);
            }}
            onMouseLeave={() => {
              setHoveredGeometry(null);
              if (setHoveredResourceId) setHoveredResourceId(null);
            }}
          >
            <div className="flex">
              {/* Thumbnail */}
              <div
                className={`${isCompact ? 'w-24' : 'w-48'} flex-shrink-0 relative group/thumb`}
              >
                {(() => {
                  // Try multiple ways to access thumbnail_url
                  const metaUi = result.meta?.ui;

                  // First try direct access
                  let thumbnailUrl =
                    metaUi?.thumbnail_url || metaUi?.['thumbnail_url'];

                  // If not found, try to extract from stringified JSON (workaround for serialization issues)
                  if (!thumbnailUrl && metaUi) {
                    try {
                      const metaUiString = JSON.stringify(metaUi);
                      const parsed = JSON.parse(metaUiString);
                      thumbnailUrl = parsed.thumbnail_url;
                    } catch (e) {
                      // Ignore parsing errors
                    }
                  }

                  // If still not found, try Object.getOwnPropertyDescriptor (for non-enumerable properties)
                  if (!thumbnailUrl && metaUi) {
                    const descriptor = Object.getOwnPropertyDescriptor(
                      metaUi,
                      'thumbnail_url'
                    );
                    if (descriptor) {
                      thumbnailUrl = descriptor.value;
                    }
                  }

                  // Last resort: check if property exists via 'in' operator
                  if (!thumbnailUrl && metaUi && 'thumbnail_url' in metaUi) {
                    thumbnailUrl = (metaUi as any).thumbnail_url;
                  }

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
                      thumbnailUrlTrimmed:
                        typeof thumbnailUrl === 'string'
                          ? thumbnailUrl.trim()
                          : 'N/A',
                      isInImageErrors: imageErrors.has(result.id),
                      metaUiKeys: metaUi ? Object.keys(metaUi) : [],
                      metaUiHasOwnProperty: metaUi
                        ? metaUi.hasOwnProperty('thumbnail_url')
                        : false,
                      metaUiIn: metaUi ? 'thumbnail_url' in metaUi : false,
                      metaUiStringified: metaUi
                        ? JSON.stringify(metaUi)
                        : 'no ui',
                    });
                  }

                  return hasThumbnail ? (
                    <div
                      className={`${isCompact ? 'h-24 w-24' : 'h-48 w-48'} rounded-l-lg`}
                    >
                      <img
                        src={toSsrThumbnailUrl(thumbnailUrl)}
                        alt={`Thumbnail for ${title}`}
                        className={`${isCompact ? 'h-24 w-24' : 'h-48 w-48'} object-cover rounded-l-lg`}
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
                          setImageErrors((prev) =>
                            new Set(prev).add(result.id)
                          );
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

                <div className="flex items-center gap-2 mb-2 pr-8">
                  <Link
                    to={`/resources/${result.id}`}
                    state={{
                      searchResults: results,
                      currentIndex: index, // Local index
                      absoluteIndex: getAbsoluteIndex(index) - 1, // Absolute index (0-based)
                      totalResults: totalResults,
                      searchUrl: location.pathname + location.search,
                      currentPage: currentPage,
                      perPage: 10, // Explicitly pass default page size
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

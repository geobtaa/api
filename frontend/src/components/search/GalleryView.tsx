import React, { useEffect, useRef } from 'react';
import type { GeoDocument } from '../../types/api';
import { Link, useLocation } from 'react-router';
import { getResourceIcon } from '../../utils/resourceIcons';
import { BookmarkButton } from '../BookmarkButton';
import { useBookmarks } from '../../context/BookmarkContext';

interface GalleryViewProps {
  results: GeoDocument[];
  isLoading: boolean;
  totalResults: number;
  currentPage: number;
  startPage?: number;
  perPage?: number;
  onLoadMore?: () => void;
  hasMore?: boolean;
}

export const GalleryView: React.FC<GalleryViewProps> = ({
  results,
  isLoading,
  totalResults,
  currentPage,
  startPage,
  perPage = 20,
  onLoadMore,
  hasMore,
}) => {
  const { isBookmarked } = useBookmarks();
  const observerTarget = useRef<HTMLDivElement>(null);
  const location = useLocation();

  // Calculate absolute index in full result set
  // Uses startPage (if provided) to determine offset of the start of the list
  const getAbsoluteIndex = (relativeIndex: number) => {
    const page = startPage || 1;
    const effectivePerPage = 20;
    const idx = (page - 1) * effectivePerPage + relativeIndex + 1;
    return { idx, page, effectivePerPage };
  };

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoading) {
          onLoadMore?.();
        }
      },
      { threshold: 0.1, rootMargin: '100px' }
    );

    const currentTarget = observerTarget.current;
    if (currentTarget) {
      observer.observe(currentTarget);
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget);
      }
    };
  }, [hasMore, onLoadMore, isLoading]);

  // Helper to get thumbnail URL consistent with SearchResults
  const getThumbnailUrl = (result: GeoDocument) => {
    const metaUi = result.meta?.ui;

    // First try direct access
    let thumbnailUrl = metaUi?.thumbnail_url || metaUi?.['thumbnail_url'];

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

    return thumbnailUrl;
  };

  const toSsrThumbnailUrl = (url: string | undefined): string | undefined => {
    if (!url || typeof url !== 'string') return undefined;

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
      return url;
    }
  };

  if (isLoading && results.length === 0) {
    return (
      <div className="flex justify-center items-center py-20">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (results.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-500">
        No results found.
      </div>
    );
  }

  return (
    <div className="flex flex-col mt-0">
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {results.map((r, index) => {
          const ogm = r.attributes.ogm;
          const title = ogm?.dct_title_s || '(Untitled)';
          const resourceClass = ogm?.gbl_resourceClass_sm?.[0];
          const thumbnailUrl = getThumbnailUrl(r);
          const ssrThumbnailUrl = toSsrThumbnailUrl(thumbnailUrl);
          const { idx: absIndex } = getAbsoluteIndex(index);
          const bookmarked = isBookmarked(r.id);

          return (
            <div
              key={r.id}
              className="group relative bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow cursor-pointer flex flex-col"
            >
              <Link
                to={`/resources/${r.id}`}
                state={{
                  searchResults: results,
                  currentIndex: index, // Local index in the current results array
                  absoluteIndex: absIndex - 1, // 0-based absolute index
                  totalResults: totalResults,
                  searchUrl: location.pathname + location.search,
                  currentPage: currentPage,
                  perPage: 20, // Explicitly pass gallery view page size
                }}
                className="flex flex-col flex-1"
              >
                <div className="aspect-square bg-gray-100 flex items-center justify-center overflow-hidden relative">
                  {ssrThumbnailUrl ? (
                    <img
                      src={ssrThumbnailUrl}
                      alt={`Thumbnail for ${title}`}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        // Handle error by hiding image and showing icon fallback
                        e.currentTarget.style.display = 'none';
                        e.currentTarget.parentElement?.classList.add(
                          'fallback-icon'
                        );
                      }}
                    />
                  ) : (
                    <div className="text-gray-400">
                      {getResourceIcon(resourceClass)}
                    </div>
                  )}

                  {/* Fallback icon container (hidden by default) */}
                  <div className="absolute inset-0 flex items-center justify-center text-gray-400 hidden fallback-icon-container">
                    {getResourceIcon(resourceClass)}
                  </div>

                  {/* Result Number Overlay - Screen Reader Only */}
                  <div className="sr-only">Result {absIndex}</div>

                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors" />

                  {/* Bookmark Button */}
                  {/* Visible if bookmarked, otherwise only on hover */}
                  <div
                    className={`absolute top-2 right-2 z-10 transition-opacity ${
                      bookmarked
                        ? 'opacity-100'
                        : 'opacity-0 group-hover:opacity-100'
                    }`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <div className="bg-white rounded-full shadow-sm hover:shadow-md">
                      <BookmarkButton itemId={r.id} />
                    </div>
                  </div>
                </div>

                <div className="p-3 flex flex-col flex-1">
                  <h3
                    className="text-sm font-semibold text-blue-600 hover:text-blue-800 line-clamp-2 mb-2 leading-snug"
                    title={typeof title === 'string' ? title : String(title)}
                  >
                    {title}
                  </h3>
                  <div className="mt-auto flex items-center justify-between text-xs text-gray-500">
                    <span>{ogm?.gbl_indexYear_im?.[0] || '-'}</span>
                    <span className="uppercase tracking-tighter opacity-70 border border-gray-200 px-1 rounded">
                      {resourceClass || 'Item'}
                    </span>
                  </div>
                </div>
              </Link>
            </div>
          );
        })}
      </div>
      {/* Sentinel for infinite scroll */}
      {hasMore && <div ref={observerTarget} className="h-10 w-full" />}
      {isLoading && results.length > 0 && (
        <div className="flex justify-center py-8 w-full">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      )}
    </div>
  );
};

import React, { useEffect, useRef } from 'react';
import type { GeoDocument } from '../../types/api';
import { Link, useLocation } from 'react-router';
import { getResourceIcon } from '../../utils/resourceIcons';
import { getResultPrimaryImageUrl } from '../../utils/resourceAssets';
import { ResultCardPill } from './ResultCardPill';
import { BookmarkButton } from '../BookmarkButton';
import { useBookmarks } from '../../context/BookmarkContext';
import { requestGalleryStateRestore } from '../../utils/galleryState';

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

  // Calculate absolute index in full result set (1-based)
  // Uses startPage (if provided) to determine offset of the start of the list
  const getAbsoluteIndex = (relativeIndex: number) => {
    const page = startPage || currentPage;
    return (page - 1) * perPage + relativeIndex + 1;
  };

  const handleResultNavigation = (event: React.MouseEvent<HTMLAnchorElement>) => {
    if (
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }

    requestGalleryStateRestore();
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
          const imageUrl = getResultPrimaryImageUrl(r, 'gallery');
          const absIndex = getAbsoluteIndex(index);
          const bookmarked = isBookmarked(r.id);

          return (
            <div
              key={r.id}
              className="group relative bg-white border border-gray-200 rounded-lg overflow-hidden hover:shadow-md transition-shadow cursor-pointer flex flex-col"
            >
              <Link
                to={`/resources/${r.id}`}
                onClick={handleResultNavigation}
                state={{
                  searchResults: results,
                  currentIndex: index, // Local index in the current results array
                  absoluteIndex: absIndex - 1, // 0-based absolute index
                  totalResults: totalResults,
                  searchUrl: location.pathname + location.search,
                  currentPage: currentPage,
                  perPage: perPage,
                }}
                className="flex flex-col flex-1"
              >
                <div className="aspect-square bg-gray-100 flex items-center justify-center overflow-hidden relative">
                  {imageUrl ? (
                    <img
                      src={imageUrl}
                      alt=""
                      className="w-full h-full object-cover"
                      decoding="async"
                      loading={index < 6 ? 'eager' : 'lazy'}
                      fetchPriority={index < 4 ? 'high' : 'auto'}
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
                    <span className="text-sm text-slate-600 dark:text-slate-400 font-semibold mr-1">
                      {absIndex}.
                    </span>
                    {title}
                  </h3>
                  <div className="mt-auto">
                    <ResultCardPill
                      indexYear={ogm?.gbl_indexYear_im?.[0]}
                      resourceClass={resourceClass}
                      provider={ogm?.schema_provider_s}
                    />
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

import React, { useEffect, useRef, useState } from 'react';
import type { GeoDocument } from '../../types/api';
import { Link, useLocation } from 'react-router';
import { getResourceIcon } from '../../utils/resourceIcons';
import { getResultPrimaryImageUrl } from '../../utils/resourceAssets';
import { ResultCardPill } from './ResultCardPill';
import { BookmarkButton } from '../BookmarkButton';
import { useBookmarks } from '../../context/BookmarkContext';
import { requestGalleryStateRestore } from '../../utils/galleryState';
import { scheduleAnalyticsBatch } from '../../services/analytics';

interface GalleryViewProps {
  results: GeoDocument[];
  isLoading: boolean;
  totalResults: number;
  currentPage: number;
  startPage?: number;
  perPage?: number;
  onLoadMore?: () => void;
  hasMore?: boolean;
  searchId?: string;
}

const INITIAL_GALLERY_IMAGE_COUNT = 10;
const DEFERRED_GALLERY_IMAGE_STAGGER_MS = 75;

function isResourceClassIconUrl(imageUrl: string | undefined): boolean {
  if (!imageUrl) return false;

  try {
    const parsed = new URL(imageUrl, 'http://localhost');
    return parsed.pathname.endsWith('/resource-class-icon');
  } catch {
    return imageUrl.includes('/resource-class-icon');
  }
}

interface GalleryThumbnailProps {
  imageUrl?: string;
  resourceClass?: string;
  index: number;
}

function GalleryThumbnail({
  imageUrl,
  resourceClass,
  index,
}: GalleryThumbnailProps) {
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [showFallback, setShowFallback] = useState(!imageUrl);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [shouldLoadImage, setShouldLoadImage] = useState(
    index < INITIAL_GALLERY_IMAGE_COUNT
  );

  const syncImageState = (image: HTMLImageElement | null) => {
    if (!image?.complete) return;

    if (image.naturalWidth > 0) {
      setImageLoaded(true);
      setShowFallback(false);
      return;
    }

    setShowFallback(true);
  };

  useEffect(() => {
    setShowFallback(!imageUrl);
    setImageLoaded(false);
  }, [imageUrl]);

  useEffect(() => {
    if (!imageUrl || shouldLoadImage) return;

    if (typeof window === 'undefined') {
      setShouldLoadImage(true);
      return;
    }

    let timeoutId: number | null = null;
    let idleCallbackId: number | null = null;

    const activate = () => {
      const delay =
        Math.max(0, index - INITIAL_GALLERY_IMAGE_COUNT) *
        DEFERRED_GALLERY_IMAGE_STAGGER_MS;
      timeoutId = window.setTimeout(() => {
        setShouldLoadImage(true);
      }, delay);
    };

    const scheduleActivation = () => {
      if ('requestIdleCallback' in window) {
        idleCallbackId = window.requestIdleCallback(activate, {
          timeout: 2000,
        });
        return;
      }
      activate();
    };

    if (document.readyState === 'complete') {
      scheduleActivation();
    } else {
      window.addEventListener('load', scheduleActivation, { once: true });
    }

    return () => {
      window.removeEventListener('load', scheduleActivation);
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      if (
        idleCallbackId !== null &&
        'cancelIdleCallback' in window &&
        typeof window.cancelIdleCallback === 'function'
      ) {
        window.cancelIdleCallback(idleCallbackId);
      }
    };
  }, [imageUrl, index, shouldLoadImage]);

  useEffect(() => {
    if (!shouldLoadImage || !imageUrl) return;
    syncImageState(imageRef.current);
  }, [imageUrl, shouldLoadImage]);

  const isResourceClassIcon = isResourceClassIconUrl(imageUrl);
  const showIconPlaceholder = !imageUrl || showFallback || !shouldLoadImage;
  const showNeutralPlaceholder =
    Boolean(imageUrl) &&
    shouldLoadImage &&
    !imageLoaded &&
    !showFallback &&
    !isResourceClassIcon;
  const priorityProps = index < 5 ? ({ fetchpriority: 'high' } as const) : {};

  return (
    <div className="aspect-square bg-gray-100 flex items-center justify-center overflow-hidden relative">
      {imageUrl && shouldLoadImage && !showFallback ? (
        <img
          ref={(image) => {
            imageRef.current = image;
            syncImageState(image);
          }}
          src={imageUrl}
          alt=""
          className={`w-full h-full object-cover transition-opacity duration-150 ${
            imageLoaded || isResourceClassIcon ? 'opacity-100' : 'opacity-0'
          }`}
          decoding="async"
          loading={index < 6 ? 'eager' : 'lazy'}
          {...priorityProps}
          onLoad={() => {
            setImageLoaded(true);
          }}
          onError={() => {
            setShowFallback(true);
          }}
        />
      ) : null}

      {showNeutralPlaceholder ? (
        <div
          data-testid={`gallery-thumbnail-loading-${index}`}
          className="absolute inset-0 bg-gray-100"
        />
      ) : null}

      {showIconPlaceholder ? (
        <div
          data-testid={`gallery-thumbnail-placeholder-${index}`}
          className="absolute inset-0 flex items-center justify-center text-gray-400"
        >
          {getResourceIcon(resourceClass)}
        </div>
      ) : null}

      <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors" />
    </div>
  );
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
  searchId,
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

  const handleResultNavigation = (
    event: React.MouseEvent<HTMLAnchorElement>,
    resourceId: string,
    label: string,
    rank: number
  ) => {
    if (
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }

    scheduleAnalyticsBatch({
      events: [
        {
          event_type: 'result_click',
          search_id: searchId,
          resource_id: resourceId,
          rank,
          page: currentPage,
          view: 'gallery',
          label,
          source_component: 'GalleryView',
          properties: {
            search_url: location.pathname + location.search,
            total_results: totalResults,
          },
        },
      ],
    });
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
                onClick={(event) =>
                  handleResultNavigation(
                    event,
                    r.id,
                    typeof title === 'string' ? title : String(title),
                    absIndex
                  )
                }
                state={{
                  searchResults: results,
                  currentIndex: index, // Local index in the current results array
                  absoluteIndex: absIndex - 1, // 0-based absolute index
                  totalResults: totalResults,
                  searchUrl: location.pathname + location.search,
                  currentPage: currentPage,
                  perPage: perPage,
                  searchId: searchId,
                  view: 'gallery',
                }}
                className="flex flex-col flex-1 relative"
              >
                <GalleryThumbnail
                  imageUrl={imageUrl}
                  resourceClass={resourceClass}
                  index={index}
                />

                <div className="sr-only">Result {absIndex}</div>

                <div className="absolute inset-0 pointer-events-none">
                  {/* Result Number Overlay - Screen Reader Only */}
                  {/* Bookmark Button */}
                  {/* Visible if bookmarked, otherwise only on hover */}
                  <div
                    className={`absolute top-2 right-2 z-10 pointer-events-auto transition-opacity ${
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

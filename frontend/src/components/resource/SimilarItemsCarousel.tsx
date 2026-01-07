import { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { GeoDocument } from '../../types/api';
import { getResourceIcon } from '../../utils/resourceIcons';

interface SimilarItemsCarouselProps {
  similarItems?: GeoDocument[];
}

interface SimilarItemCardProps {
  item: GeoDocument;
}

function SimilarItemCard({ item }: SimilarItemCardProps) {
  const [imageError, setImageError] = useState(false);

  // Safely extract values with fallbacks
  const title =
    item?.attributes?.ogm?.dct_title_s ||
    (item as unknown as { title?: string })?.title ||
    'Untitled';

  // Try multiple possible paths for thumbnail URL
  const thumbnailUrl =
    item?.meta?.ui?.thumbnail_url ||
    (item as unknown as { thumbnail_url?: string })?.thumbnail_url ||
    (item as unknown as { meta?: { thumbnail_url?: string } })?.meta
      ?.thumbnail_url;

  const resourceClass = item?.attributes?.ogm?.gbl_resourceClass_sm?.[0];
  const provider = item?.attributes?.ogm?.schema_provider_s;

  // Debug logging for thumbnail URLs - must be before early return
  useEffect(() => {
    if (item?.id) {
      console.log(`SimilarItemCard [${item.id}] thumbnail check:`, {
        'item.meta?.ui?.thumbnail_url': item.meta?.ui?.thumbnail_url,
        'final thumbnailUrl': thumbnailUrl,
        imageError: imageError,
        'full item structure': item,
      });
    }
  }, [item, thumbnailUrl, imageError]);

  // Safety checks - after hooks
  if (!item || !item.id) {
    return null;
  }

  try {
    return (
      <Link
        to={`/resources/${item.id}`}
        className="group bg-white rounded-lg border border-gray-200 hover:border-blue-500 hover:shadow-lg transition-all overflow-hidden"
      >
        {/* Image Container */}
        <div className="aspect-video w-full bg-gray-50 relative overflow-hidden">
          {thumbnailUrl &&
          typeof thumbnailUrl === 'string' &&
          thumbnailUrl.trim() !== '' &&
          !imageError ? (
            <img
              src={thumbnailUrl}
              alt={title}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              onError={(e) => {
                console.error(
                  `Failed to load thumbnail for ${item.id}:`,
                  thumbnailUrl,
                  e
                );
                setImageError(true);
              }}
              onLoad={() => {
                console.log(
                  `Successfully loaded thumbnail for ${item.id}:`,
                  thumbnailUrl
                );
              }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center bg-gray-50">
              {getResourceIcon(resourceClass)}
            </div>
          )}
        </div>

        {/* Content */}
        <div className="p-4">
          <h3 className="text-sm font-medium text-gray-900 line-clamp-2 group-hover:text-blue-600 transition-colors">
            {title}
          </h3>
          {provider && (
            <p className="text-xs text-gray-500 mt-1 line-clamp-1">
              {provider}
            </p>
          )}
        </div>
      </Link>
    );
  } catch (error) {
    console.error('Error rendering SimilarItemCard:', error, item);
    return null;
  }
}

export function SimilarItemsCarousel({
  similarItems,
}: SimilarItemsCarouselProps) {
  const [currentPage, setCurrentPage] = useState(0);
  const itemsPerPage = 4;

  // Reset to first page when similar items change
  useEffect(() => {
    setCurrentPage(0);
  }, [similarItems]);

  // Debug logging
  useEffect(() => {
    if (similarItems) {
      console.log('SimilarItemsCarousel - similarItems structure:', {
        isArray: Array.isArray(similarItems),
        length: similarItems.length,
        firstItem: similarItems[0],
        sample: similarItems.slice(0, 2),
      });
    }
  }, [similarItems]);

  if (
    !similarItems ||
    !Array.isArray(similarItems) ||
    similarItems.length === 0
  ) {
    return null;
  }

  // Filter out any invalid items
  const validItems = similarItems.filter(
    (item) => item && typeof item === 'object' && item.id
  );

  if (validItems.length === 0) {
    console.warn('SimilarItemsCarousel - No valid items found after filtering');
    return null;
  }

  const totalPages = Math.ceil(validItems.length / itemsPerPage);
  const startIndex = currentPage * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentItems = validItems.slice(startIndex, endIndex);

  const handlePrev = () => {
    setCurrentPage((prev) => Math.max(0, prev - 1));
  };

  const handleNext = () => {
    setCurrentPage((prev) => Math.min(totalPages - 1, prev + 1));
  };

  return (
    <div className="w-full bg-white rounded-lg shadow-md overflow-hidden my-8">
      <div className="px-6 py-4 border-b border-gray-200">
        <h2 className="text-xl font-semibold text-gray-900">Similar Items</h2>
      </div>

      <div className="relative px-6 py-6">
        {/* Carousel Container */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {currentItems
            .filter((item) => item && item.id)
            .map((item) => (
              <SimilarItemCard key={item.id} item={item} />
            ))}
        </div>

        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-6">
            <button
              onClick={handlePrev}
              disabled={currentPage === 0}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              aria-label="Previous page"
            >
              <ChevronLeft className="w-4 h-4" />
              Previous
            </button>

            <div className="flex items-center gap-2">
              {Array.from({ length: totalPages }, (_, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentPage(i)}
                  className={`w-2 h-2 rounded-full transition-colors ${
                    i === currentPage
                      ? 'bg-blue-600'
                      : 'bg-gray-300 hover:bg-gray-400'
                  }`}
                  aria-label={`Go to page ${i + 1}`}
                  aria-current={i === currentPage ? 'page' : undefined}
                />
              ))}
            </div>

            <button
              onClick={handleNext}
              disabled={currentPage === totalPages - 1}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              aria-label="Next page"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

import { useEffect, useRef, useState } from 'react';
import type { GeoDocument } from '../../types/api';
import { getResultStaticMapUrl } from '../../utils/resourceAssets';

interface StaticResultMapProps {
  result: GeoDocument;
}

export function StaticResultMap({ result }: StaticResultMapProps) {
  const [imageError, setImageError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const imageUrl = getResultStaticMapUrl(result);

  // If we navigate between result sets, reset loading/error state.
  useEffect(() => {
    setImageError(false);
    setIsLoading(true);
  }, [result.id, imageUrl]);

  // Handle cases where the image is already in the browser cache and the `load`
  // event can fire before React attaches the handler.
  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;
    if (img.complete && img.naturalWidth > 0) {
      setIsLoading(false);
    }
  }, [result.id, imageUrl]);

  // If image failed to load, show placeholder
  if (imageError) {
    return (
      <div className="h-48 w-48 flex items-center justify-center bg-gray-50 rounded-r-lg">
        <span className="text-xs text-gray-400">Map unavailable</span>
      </div>
    );
  }

  return (
    <div className="h-48 w-48 rounded-r-lg overflow-hidden relative">
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-50">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
        </div>
      )}
      <img
        ref={imgRef}
        src={imageUrl}
        alt=""
        loading="lazy"
        decoding="async"
        {...({ fetchpriority: 'low' } as const)}
        className={`h-full w-full object-cover transition-opacity duration-150 ${
          isLoading ? 'opacity-0' : 'opacity-100'
        }`}
        onLoad={() => setIsLoading(false)}
        onError={() => {
          setIsLoading(false);
          setImageError(true);
        }}
      />
    </div>
  );
}

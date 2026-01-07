import { useState } from 'react';
import type { GeoDocument } from '../../types/api';
import { getApiBasePath } from '../../services/api';

interface StaticResultMapProps {
  result: GeoDocument;
}

export function StaticResultMap({ result }: StaticResultMapProps) {
  const [imageError, setImageError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const geometry = result.meta?.ui?.viewer?.geometry;

  // Build static map URL
  // Authentication is handled by the NGINX BFF proxy server-side
  const getStaticMapUrl = (): string => {
    const apiBasePath = getApiBasePath();
    const baseUrl = `${apiBasePath}/resources/${result.id}/static-map`;
    
    // Create URL object - all URLs are absolute (pointing to BFF proxy)
    const url = new URL(baseUrl);
    
    return url.toString();
  };

  // If no geometry, show placeholder
  if (!geometry) {
    return (
      <div className="h-48 w-48 flex items-center justify-center bg-gray-50 rounded-r-lg">
        <span className="text-xs text-gray-400">No map data</span>
      </div>
    );
  }

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
        src={getStaticMapUrl()}
        alt={`Map for ${result.attributes.ogm.dct_title_s}`}
        className="h-full w-full object-cover"
        onLoad={() => setIsLoading(false)}
        onError={() => {
          setIsLoading(false);
          setImageError(true);
        }}
        style={{ display: isLoading ? 'none' : 'block' }}
      />
    </div>
  );
}

import { useState } from 'react';
import type { GeoDocument } from '../../types/api';

interface StaticResultMapProps {
  result: GeoDocument;
}

function coerceToSameOriginPath(url: string): string {
  // Prefer relative URLs so images work behind proxies and avoid mixed-content issues.
  // If the URL is absolute and same-origin, strip to path+search.
  try {
    const u = new URL(url, typeof window !== 'undefined' ? window.location.origin : 'http://localhost');
    if (typeof window !== 'undefined' && u.origin === window.location.origin) {
      return `${u.pathname}${u.search}`;
    }
    return u.toString();
  } catch {
    return url;
  }
}

export function StaticResultMap({ result }: StaticResultMapProps) {
  const [imageError, setImageError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const geometry = result.meta?.ui?.viewer?.geometry;

  // Build static map URL
  // Prefer the API-provided static map URL (meta.ui.static_map), otherwise fall back
  // to the public API endpoint. This avoids relying on the frontend SSR "static-map"
  // resource route, which may not be present in all deployments.
  const getStaticMapUrl = (): string => {
    const apiProvided = (result.meta as any)?.ui?.static_map as string | undefined;
    const fallback = `/api/v1/resources/${result.id}/static-map`;
    return coerceToSameOriginPath(apiProvided || fallback);
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

import React, { Suspense, useState, useEffect } from 'react';

// Leaflet/react-leaflet require `window`, so we lazy-load the real implementation.
const MapPageClient = React.lazy(() => import('./MapPage.client'));

const LoadingFallback = () => (
  <div className="min-h-screen bg-gray-50 flex items-center justify-center">
    <div className="text-gray-600">Loading map…</div>
  </div>
);

export function MapPage() {
  // Start with false on both server and client to ensure hydration matches.
  // After hydration, useEffect sets it to true to trigger client-only render.
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  // Server and initial client render both show the same fallback.
  if (!isClient) {
    return <LoadingFallback />;
  }

  // After hydration, render the lazy-loaded client component.
  return (
    <Suspense fallback={<LoadingFallback />}>
      <MapPageClient />
    </Suspense>
  );
}

export default MapPage;

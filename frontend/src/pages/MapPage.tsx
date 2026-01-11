import React, { Suspense } from "react";

// Leaflet/react-leaflet require `window`, so we lazy-load the real implementation
// and render nothing during SSR.
const MapPageClient = React.lazy(() => import("./MapPage.client"));

export function MapPage() {
  if (typeof window === "undefined") {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading…</div>
      </div>
    );
  }

  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <div className="text-gray-600">Loading…</div>
        </div>
      }
    >
      <MapPageClient />
    </Suspense>
  );
}

export default MapPage;


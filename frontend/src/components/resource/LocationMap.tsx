import React, { Suspense, useEffect, useState } from 'react';

interface LocationMapProps {
  geometry:
    | string
    | GeoJSON.Polygon
    | GeoJSON.MultiPolygon
    | { wkt: string }
    | null;
}

const LocationMapClient = React.lazy(() => import('./LocationMap.client'));

export const LocationMap: React.FC<LocationMapProps> = ({ geometry }) => {
  // Prevent hydration mismatches: render deterministic placeholder on the server
  // and on the client's first render. Then swap in the Leaflet map after mount.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <div className="text-gray-500" aria-hidden="true">
        Loading map…
      </div>
    );
  }

  return (
    <Suspense fallback={null}>
      <LocationMapClient geometry={geometry} />
    </Suspense>
  );
};

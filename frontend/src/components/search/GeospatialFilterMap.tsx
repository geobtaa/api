import React, { Suspense, useEffect, useState } from 'react';

const GeospatialFilterMapClient = React.lazy(
  () => import('./GeospatialFilterMap.client')
);

interface GeospatialFilterMapProps {
  /** When true, hide the "Location" heading and Clear button (e.g. when used inside LocationFacetCollapsible). */
  hideHeading?: boolean;
}

export function GeospatialFilterMap({ hideHeading }: GeospatialFilterMapProps) {
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
      <GeospatialFilterMapClient hideHeading={hideHeading} />
    </Suspense>
  );
}

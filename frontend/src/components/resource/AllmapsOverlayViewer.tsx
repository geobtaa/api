import React, { Suspense, useEffect, useState } from 'react';
import type { AllmapsAttributes } from '../../utils/allmaps';

type AllmapsGeometry =
  | string
  | GeoJSON.Geometry
  | GeoJSON.Feature
  | { wkt: string }
  | null
  | undefined;

interface AllmapsOverlayViewerProps {
  allmaps: AllmapsAttributes | null | undefined;
  geometry?: AllmapsGeometry;
}

const AllmapsOverlayViewerClient = React.lazy(
  () => import('./AllmapsOverlayViewer.client')
);

export function AllmapsOverlayViewer(props: AllmapsOverlayViewerProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!mounted) {
    return (
      <div className="h-[600px] bg-gray-100 text-sm text-gray-500">
        Loading overlay...
      </div>
    );
  }

  return (
    <Suspense fallback={null}>
      <AllmapsOverlayViewerClient {...props} />
    </Suspense>
  );
}

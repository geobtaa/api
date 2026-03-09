import React, { Suspense, useEffect, useState } from 'react';
import type { GeoDocument } from '../../types/api';

const MapResultViewClient = React.lazy(() =>
  import('./MapResultView.client').then((module) => ({
    default: module.MapResultView,
  }))
);

interface MapResultViewProps {
  results: GeoDocument[];
  highlightedResourceId?: string | null;
  highlightedGeometry?: string | null;
  resultStartIndex?: number;
}

export function MapResultView(props: MapResultViewProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="h-full w-full bg-slate-100 rounded-lg animate-pulse flex items-center justify-center text-slate-400">
        Loading map...
      </div>
    );
  }

  return (
    <Suspense
      fallback={
        <div className="h-full w-full bg-slate-100 rounded-lg animate-pulse flex items-center justify-center text-slate-400">
          Loading map...
        </div>
      }
    >
      <MapResultViewClient {...props} />
    </Suspense>
  );
}

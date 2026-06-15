import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { attachBasemapSwitcher } from '../../config/basemaps';
import { leafletGestureMapOptions } from '../../config/leafletConfig';
import { registerLeafletGestureHandling } from '../../config/leafletGestureHandling';
import { getBboxFromGeometry } from '../../utils/geometryUtils';
import {
  type AllmapsAttributes,
  getAllmapsAnnotationUrl,
} from '../../utils/allmaps';

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

const DEFAULT_OPACITY = 0.75;
const DEFAULT_CENTER: L.LatLngExpression = [44.5, -89.5];

function getGeometryBounds(geometry: AllmapsGeometry): L.LatLngBounds | null {
  const bbox = getBboxFromGeometry(
    geometry as Parameters<typeof getBboxFromGeometry>[0]
  );
  if (!bbox) return null;

  const bounds = L.latLngBounds(bbox[0], bbox[1]);
  return bounds.isValid() ? bounds : null;
}

function getLayerBounds(layer: unknown): L.LatLngBounds | null {
  const layerWithBounds = layer as {
    getBounds?: () => L.LatLngBounds | null | undefined;
  };

  try {
    const bounds = layerWithBounds.getBounds?.();
    return bounds?.isValid?.() ? bounds : null;
  } catch {
    return null;
  }
}

export function AllmapsOverlayViewer({
  allmaps,
  geometry,
}: AllmapsOverlayViewerProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const basemapCleanupRef = useRef<(() => void) | null>(null);
  const layerRef = useRef<{ setOpacity?: (opacity: number) => void } | null>(
    null
  );
  const [opacity, setOpacity] = useState(DEFAULT_OPACITY);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const annotationUrl = useMemo(
    () => getAllmapsAnnotationUrl(allmaps),
    [allmaps]
  );

  useEffect(() => {
    const container = mapContainerRef.current;
    if (!container || !annotationUrl) {
      setIsLoading(false);
      setError(annotationUrl ? null : 'Map overlay is not available.');
      return;
    }

    let cancelled = false;
    let removeWarpedMapListener: (() => void) | null = null;
    const fitTimeouts: number[] = [];
    setIsLoading(true);
    setError(null);

    registerLeafletGestureHandling(L);
    const map = L.map(container, {
      ...leafletGestureMapOptions,
      zoomAnimationThreshold: 1,
      worldCopyJump: true,
    }).setView(DEFAULT_CENTER, 5);
    mapRef.current = map;
    basemapCleanupRef.current = attachBasemapSwitcher(map, L);

    const fallbackBounds = getGeometryBounds(geometry);
    if (fallbackBounds) {
      map.fitBounds(fallbackBounds, { padding: [24, 24] });
    }

    const refitToLayer = () => {
      if (cancelled || !layerRef.current) return;
      const layerBounds = getLayerBounds(layerRef.current);
      if (layerBounds) {
        map.fitBounds(layerBounds, {
          padding: [28, 28],
          maxZoom: 15,
        });
      } else if (fallbackBounds) {
        map.fitBounds(fallbackBounds, { padding: [24, 24] });
      }
      map.invalidateSize();
    };

    async function addAllmapsLayer() {
      try {
        const { WarpedMapLayer } = await import('@allmaps/leaflet');
        if (cancelled) return;

        const layer = new WarpedMapLayer(annotationUrl, {
          opacity: DEFAULT_OPACITY,
        });
        layerRef.current = layer as {
          setOpacity?: (opacity: number) => void;
        };

        map.on('warpedmapadded', refitToLayer);
        removeWarpedMapListener = () => map.off('warpedmapadded', refitToLayer);

        layer.addTo(map);
        window.requestAnimationFrame(() => {
          if (!cancelled) {
            map.invalidateSize();
            refitToLayer();
          }
        });
        [300, 900, 1600].forEach((delay) => {
          fitTimeouts.push(
            window.setTimeout(() => {
              refitToLayer();
            }, delay)
          );
        });
      } catch (err) {
        if (!cancelled) {
          console.warn('Allmaps overlay failed to load:', err);
          setError('Unable to load the Allmaps overlay.');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void addAllmapsLayer();

    return () => {
      cancelled = true;
      fitTimeouts.forEach((id) => window.clearTimeout(id));
      removeWarpedMapListener?.();
      basemapCleanupRef.current?.();
      basemapCleanupRef.current = null;
      layerRef.current = null;
      map.remove();
      mapRef.current = null;
    };
  }, [annotationUrl, geometry]);

  useEffect(() => {
    layerRef.current?.setOpacity?.(opacity);
  }, [opacity]);

  return (
    <div className="pa11y-ignore-map-contrast">
      <div className="border-b border-gray-200 bg-white px-4 py-3">
        <h2 className="text-base font-semibold text-gray-900">
          Allmaps georeferenced map overlay
        </h2>
      </div>
      <div className="relative h-[600px] w-full bg-gray-100">
        <div ref={mapContainerRef} className="h-full w-full" />

        <label className="absolute bottom-4 left-4 z-[500] flex items-center gap-2 rounded-md border border-gray-200 bg-white/95 px-3 py-2 text-xs font-medium text-gray-700 shadow-sm">
          <span>Opacity</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opacity}
            onChange={(event) => setOpacity(Number(event.target.value))}
            className="w-28 accent-blue-600"
            aria-label="Allmaps overlay opacity"
          />
          <span className="w-8 text-right">{Math.round(opacity * 100)}%</span>
        </label>

        {isLoading && (
          <div className="absolute inset-0 z-[450] flex items-center justify-center bg-white/70 text-sm font-medium text-gray-600">
            Loading overlay...
          </div>
        )}

        {error && (
          <div className="absolute inset-x-4 top-4 z-[500] rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-sm">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}

export default AllmapsOverlayViewer;

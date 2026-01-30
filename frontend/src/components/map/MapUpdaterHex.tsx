import { useCallback, useEffect, useState } from 'react';
import { GeoJSON, useMap, useMapEvents } from 'react-leaflet';
import { cellToBoundary } from 'h3-js';
import type { MapFeatureClickPayload } from '../../types/map';
import { useMapH3 } from '../../hooks/useMapH3';
import { formatCount } from '../../utils/formatNumber';

/** Map Leaflet zoom to H3 resolution so hex size changes more visibly when zooming (e.g. into Chicago). */
function zoomToResolution(zoom: number): number {
  if (zoom <= 3) return 2;
  if (zoom <= 4) return 3;
  if (zoom <= 6) return 4;
  if (zoom <= 8) return 5;
  if (zoom <= 10) return 6;
  if (zoom <= 12) return 7;
  return 8;
}

/** Zoom at or below this level may request global hexes (no bbox) when bbox is not yet available. */
const ZOOM_GLOBAL_THRESHOLD = 5;

/** Clamp longitude to [-180, 180] and latitude to [-90, 90] for ES geo_bounding_box. */
function clampBbox(
  west: number,
  south: number,
  east: number,
  north: number
): string {
  const clampLon = (x: number) => Math.max(-180, Math.min(180, x));
  const clampLat = (x: number) => Math.max(-90, Math.min(90, x));
  const w = clampLon(west);
  const s = clampLat(south);
  const e = clampLon(east);
  const n = clampLat(north);
  return `${w},${s},${e},${n}`;
}

/** True if the H3 cell's boundary intersects the given Leaflet bounds. */
function hexIntersectsBounds(
  h3Index: string,
  bounds: { getWest: () => number; getSouth: () => number; getEast: () => number; getNorth: () => number }
): boolean {
  const vs = cellToBoundary(h3Index);
  const lats = vs.map(([lat]) => lat);
  const lngs = vs.map(([, lng]) => lng);
  const hexSouth = Math.min(...lats);
  const hexNorth = Math.max(...lats);
  const hexWest = Math.min(...lngs);
  const hexEast = Math.max(...lngs);
  const w = bounds.getWest();
  const s = bounds.getSouth();
  const e = bounds.getEast();
  const n = bounds.getNorth();
  return !(hexEast < w || hexWest > e || hexNorth < s || hexSouth > n);
}

/** 10-step blue ramp (light to dark) for resource density. */
const HEX_RAMP_COLORS = [
  '#DBEAFE', '#BFDBFE', '#93C5FD', '#7AB3FD', '#60A5FA',
  '#3B82F6', '#2563EB', '#1D4ED8', '#1E40AF', '#003C5B',
];
const HEX_RAMP_THRESHOLDS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9];

function getColor(intensity: number): string {
  for (let i = 0; i < HEX_RAMP_THRESHOLDS.length; i++) {
    if (intensity <= HEX_RAMP_THRESHOLDS[i]) return HEX_RAMP_COLORS[i];
  }
  return HEX_RAMP_COLORS[HEX_RAMP_COLORS.length - 1];
}

export function MapUpdaterHex({
  searchQuery,
  onFeatureClick,
  onHexData,
  queryString,
}: {
  searchQuery: string;
  onFeatureClick: (feature: MapFeatureClickPayload) => void;
  onHexData?: (stats: {
    hexCount: number;
    totalInView: number;
    loading: boolean;
    error: string | null;
  }) => void;
  queryString?: string;
}) {
  const map = useMap();
  const [bbox, setBbox] = useState<string | null>(null);

  const updateBbox = useCallback(() => {
    const b = map.getBounds();
    setBbox(
      clampBbox(b.getWest(), b.getSouth(), b.getEast(), b.getNorth())
    );
  }, [map]);

  useMapEvents({
    moveend: updateBbox,
    zoomend: updateBbox,
  });

  useEffect(() => {
    const ready = new Promise<void>((resolve) => {
      map.whenReady(resolve);
    });
    ready.then(() => updateBbox());
  }, [map, updateBbox]);

  const zoom = map.getZoom();
  const resolution = zoomToResolution(zoom);
  // Prefer viewport bbox when available so we get hexes for the visible area and they always render.
  // Only use global (null bbox) when zoomed out and bbox not yet set (e.g. before whenReady).
  const useGlobalRequest =
    zoom <= ZOOM_GLOBAL_THRESHOLD && bbox === null;
  const bboxForApi = useGlobalRequest ? null : bbox;
  const {
    hexes,
    hexCount,
    totalInView,
    loading,
    error,
  } = useMapH3(searchQuery, bboxForApi, resolution, queryString);

  useEffect(() => {
    if (onHexData)
      onHexData({ hexCount, totalInView, loading, error });
  }, [onHexData, hexCount, totalInView, loading, error]);

  if (error) return null;
  // Show empty layer while loading instead of hiding (so hexes appear as soon as data arrives)
  let hexesToRender = loading && hexes.length === 0 ? [] : hexes;
  // When we requested global (no bbox), filter to current viewport so we only draw visible hexes.
  if (useGlobalRequest && hexesToRender.length > 0) {
    const bounds = map.getBounds();
    const isValid =
      typeof bounds.isValid === 'function' && bounds.isValid();
    const hasExtent =
      bounds.getNorth() - bounds.getSouth() > 0.1 &&
      bounds.getEast() - bounds.getWest() > 0.1;
    if (isValid && hasExtent) {
      hexesToRender = hexesToRender.filter((h) => hexIntersectsBounds(h.h3, bounds));
    }
  }

  const maxCount = Math.max(...hexesToRender.map((h) => h.count), 1);
  const features = hexesToRender.map((h) => {
    const vs = cellToBoundary(h.h3);
    const ring = vs.map(([lat, lng]) => [lng, lat] as [number, number]);
    ring.push(ring[0]);
    return {
      type: 'Feature' as const,
      properties: { h3: h.h3, count: h.count },
      geometry: {
        type: 'Polygon' as const,
        coordinates: [ring],
      },
    };
  });

  const fc = { type: 'FeatureCollection' as const, features };

  // react-leaflet GeoJSON does not update when data changes; key forces remount so hexes redraw
  const geoKey = `${bbox ?? ''}-${resolution}-${features.length}`;

  return (
    <GeoJSON
      key={geoKey}
      data={fc}
      style={(feature) => {
        const c = feature?.properties?.count ?? 0;
        const intensity = c / maxCount;
        return {
          fillColor: getColor(intensity),
          weight: 1,
          opacity: 1,
          color: 'white',
          fillOpacity: 0.7,
        };
      }}
      onEachFeature={(feature, layer) => {
        const count = feature?.properties?.count ?? 0;
        const h3 = feature?.properties?.h3 ?? '';
        const params = new URLSearchParams();
        if (searchQuery) params.set('q', searchQuery);
        params.set(`include_filters[h3_res${resolution}][]`, h3);
        const searchUrl = `/search?${params.toString()}`;
        layer.bindPopup(
          `<div class="map-hex-popup"><h3 class="text-sm font-semibold mb-1">H3 ${h3}</h3><p class="text-sm mb-2"><strong>Resources:</strong> ${formatCount(count)}</p><a href="${searchUrl}" class="text-blue-600 hover:underline text-sm">Search this hex</a></div>`
        );
        layer.on('click', () =>
          onFeatureClick({ properties: { name: `Hex ${h3.slice(-6)}`, hits: count } })
        );
      }}
    />
  );
}

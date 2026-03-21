import { useCallback, useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { GeoJSON, useMap, useMapEvents } from 'react-leaflet';
import { cellArea, cellToBoundary, UNITS } from 'h3-js';
import type { MapFeatureClickPayload } from '../../types/map';
import { useMapH3 } from '../../hooks/useMapH3';
import { formatCount } from '../../utils/formatNumber';
import { zoomToResolution } from '../../utils/h3Resolution';
import { buildSearchUrl } from '../../utils/h3SearchUrl';

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
  bounds: {
    getWest: () => number;
    getSouth: () => number;
    getEast: () => number;
    getNorth: () => number;
  }
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
  '#DBEAFE',
  '#BFDBFE',
  '#93C5FD',
  '#7AB3FD',
  '#60A5FA',
  '#3B82F6',
  '#2563EB',
  '#1D4ED8',
  '#1E40AF',
  '#003C5B',
];
const HEX_RAMP_THRESHOLDS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9];

function getColor(intensity: number): string {
  for (let i = 0; i < HEX_RAMP_THRESHOLDS.length; i++) {
    if (intensity <= HEX_RAMP_THRESHOLDS[i]) return HEX_RAMP_COLORS[i];
  }
  return HEX_RAMP_COLORS[HEX_RAMP_COLORS.length - 1];
}

export type HexHoverData = { h3: string; count: number; resolution: number };

function formatAreaKm2(km2: number): string {
  if (km2 >= 1000)
    return km2.toLocaleString('en-US', { maximumFractionDigits: 0 });
  if (km2 >= 1)
    return km2.toLocaleString('en-US', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 2,
    });
  return km2.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
}

export function MapUpdaterHex({
  searchQuery,
  onFeatureClick,
  onHexClick,
  enableSearchPopup = false,
  onHexData,
  onHexHover,
  hoveredHex,
  queryString,
}: {
  searchQuery: string;
  onFeatureClick: (feature: MapFeatureClickPayload) => void;
  onHexClick?: (data: { h3: string; count: number; resolution: number }) => void;
  enableSearchPopup?: boolean;
  onHexData?: (stats: {
    hexCount: number;
    totalInView: number;
    loading: boolean;
    error: string | null;
    hexes: Array<{ h3: string; count: number }>;
    resolution: number;
  }) => void;
  onHexHover?: (data: HexHoverData | null) => void;
  hoveredHex?: HexHoverData | null;
  queryString?: string;
}) {
  const map = useMap();
  const [bbox, setBbox] = useState<string | null>(null);
  const hoveredRef = useRef<{
    layer: L.Path;
    defaultStyle: L.PathOptions;
  } | null>(null);
  const prevHoveredHexRef = useRef<HexHoverData | null | undefined>(undefined);

  const openSearchPopup = useCallback(
    (layer: L.Layer, h3: string, count: number, popupResolution: number) => {
      if (!(layer instanceof L.Path)) return;
      let areaMarkup = '';
      try {
        const areaKm2 = cellArea(h3, UNITS.km2);
        areaMarkup =
          `<div class="flex justify-between gap-4">` +
          `<dt class="font-medium">Area</dt>` +
          `<dd>${formatAreaKm2(areaKm2)} km²</dd>` +
          `</div>`;
      } catch {
        // Invalid H3 index or library error
      }
      const searchUrl = buildSearchUrl(
        h3,
        popupResolution,
        searchQuery,
        queryString
      );
      const popupHtml =
        `<div class="rounded-lg border border-gray-200 bg-white/95 shadow-lg backdrop-blur-sm p-3 min-w-[180px]">` +
        `<h3 class="text-sm font-semibold text-gray-900 mb-1">H3 ${h3}</h3>` +
        `<dl class="text-sm text-gray-600 space-y-1 mb-2">` +
        `<div class="flex justify-between gap-4">` +
        `<dt class="font-medium">Resources</dt>` +
        `<dd>${formatCount(count)}</dd>` +
        `</div>` +
        `<div class="flex justify-between gap-4">` +
        `<dt class="font-medium">Resolution</dt>` +
        `<dd>Level ${popupResolution}</dd>` +
        `</div>` +
        areaMarkup +
        `</dl>` +
        `<a href="${searchUrl}" class="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline">Search this hex</a>` +
        `</div>`;
      layer.bindPopup(popupHtml, {
        autoPan: false,
        closeButton: false,
        autoClose: true,
        closeOnClick: true,
        className: 'map-hex-search-popup',
      });
      layer.openPopup();
    },
    [queryString, searchQuery]
  );

  const updateBbox = useCallback(() => {
    const b = map.getBounds();
    setBbox(clampBbox(b.getWest(), b.getSouth(), b.getEast(), b.getNorth()));
  }, [map]);

  useMapEvents({
    moveend: updateBbox,
    zoomend: updateBbox,
  });

  useEffect(() => {
    map.whenReady(() => updateBbox());
  }, [map, updateBbox]);

  const zoom = map.getZoom();
  const resolution = zoomToResolution(zoom);
  // Skip global (null bbox) request at low zoom: it can be cached empty. Wait for moveend to set bbox.
  const useGlobalRequest = zoom <= ZOOM_GLOBAL_THRESHOLD && bbox === null;
  const bboxForApi = useGlobalRequest ? null : bbox;
  const fetchEnabled = !useGlobalRequest;
  const { hexes, hexCount, totalInView, loading, error } = useMapH3(
    searchQuery,
    bboxForApi,
    resolution,
    queryString,
    { enabled: fetchEnabled }
  );

  useEffect(() => {
    if (onHexData)
      onHexData({ hexCount, totalInView, loading, error, hexes, resolution });
  }, [onHexData, hexCount, totalInView, loading, error, hexes, resolution]);

  useEffect(() => {
    if (!onHexHover) return;
    const container = map.getContainer();
    const onLeave = (e: MouseEvent) => {
      const related = e.relatedTarget as Node | null;
      if (
        related &&
        typeof (related as Element).closest === 'function' &&
        (related as Element).closest('[data-hex-popover]')
      )
        return;
      const current = hoveredRef.current;
      if (current) {
        current.layer.setStyle(current.defaultStyle);
        onHexHover(null);
        hoveredRef.current = null;
      }
    };
    container.addEventListener('mouseleave', onLeave as EventListener);
    return () =>
      container.removeEventListener('mouseleave', onLeave as EventListener);
  }, [map, onHexHover]);

  useEffect(() => {
    if (
      onHexHover &&
      hoveredHex === null &&
      prevHoveredHexRef.current != null
    ) {
      const current = hoveredRef.current;
      if (current) {
        current.layer.setStyle(current.defaultStyle);
        hoveredRef.current = null;
      }
    }
    prevHoveredHexRef.current = hoveredHex;
  }, [onHexHover, hoveredHex]);

  if (error) return null;
  // Show empty layer while loading instead of hiding (so hexes appear as soon as data arrives)
  let hexesToRender = loading && hexes.length === 0 ? [] : hexes;
  // When we requested global (no bbox), filter to current viewport so we only draw visible hexes.
  if (useGlobalRequest && hexesToRender.length > 0) {
    const bounds = map.getBounds();
    const isValid = typeof bounds.isValid === 'function' && bounds.isValid();
    const hasExtent =
      bounds.getNorth() - bounds.getSouth() > 0.1 &&
      bounds.getEast() - bounds.getWest() > 0.1;
    if (isValid && hasExtent) {
      hexesToRender = hexesToRender.filter((h) =>
        hexIntersectsBounds(h.h3, bounds)
      );
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
        const h3 = feature?.properties?.h3 ?? '';
        const intensity =
          maxCount > 0 ? Math.log(c + 1) / Math.log(maxCount + 1) : 0;
        const base = {
          fillColor: getColor(intensity),
          weight: 1,
          opacity: 1,
          color: 'white',
          fillOpacity: 0.7,
          className: '' as string,
        };
        if (hoveredHex && h3 === hoveredHex.h3) {
          return {
            ...base,
            color: '#3B82F6',
            weight: 3,
            className: 'hex-hover-glow',
          };
        }
        return base;
      }}
      onEachFeature={(feature, layer) => {
        const count = feature?.properties?.count ?? 0;
        const h3 = feature?.properties?.h3 ?? '';
        const c = feature?.properties?.count ?? 0;
        const intensity =
          maxCount > 0 ? Math.log(c + 1) / Math.log(maxCount + 1) : 0;
        const defaultStyle = {
          fillColor: getColor(intensity),
          weight: 1,
          opacity: 1,
          color: 'white',
          fillOpacity: 0.7,
          className: '',
        };
        const hoverStyle = {
          ...defaultStyle,
          color: '#3B82F6',
          weight: 3,
          className: 'hex-hover-glow',
        };

        if (!onHexHover) {
          const params = new URLSearchParams();
          if (searchQuery) params.set('q', searchQuery);
          params.set(`include_filters[h3_res${resolution}][]`, h3);
          const searchUrl = `/search?${params.toString()}`;
          layer.bindPopup(
            `<div class="map-hex-popup"><h3 class="text-sm font-semibold mb-1">H3 ${h3}</h3><p class="text-sm mb-2"><strong>Resources:</strong> ${formatCount(count)}</p><a href="${searchUrl}" class="text-blue-600 hover:underline text-sm">Search this hex</a></div>`
          );
        }

        layer.on('mouseover', () => {
          const prev = hoveredRef.current;
          if (prev && prev.layer !== layer) {
            prev.layer.setStyle(prev.defaultStyle);
          }
          (layer as L.Path).setStyle(hoverStyle);
          layer.bringToFront();
          hoveredRef.current = { layer: layer as L.Path, defaultStyle };
          onHexHover?.({ h3, count, resolution });
        });
        layer.on('mouseout', () => {
          const current = hoveredRef.current;
          if (current && current.layer === layer) {
            current.layer.setStyle(current.defaultStyle);
            hoveredRef.current = null;
            onHexHover?.(null);
          }
        });
        layer.on('click', (event: L.LeafletMouseEvent) => {
          if (event.originalEvent.ctrlKey || event.originalEvent.metaKey) {
            return;
          }
          if (enableSearchPopup) {
            L.DomEvent.stopPropagation(event);
            openSearchPopup(layer, h3, count, resolution);
            return;
          }
          if (onHexClick) {
            onHexClick({ h3, count, resolution });
            return;
          }
          onFeatureClick({
            properties: { name: `Hex ${h3.slice(-6)}`, hits: count },
          });
        });
      }}
    />
  );
}

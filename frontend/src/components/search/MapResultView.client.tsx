import React, { useEffect, useMemo, useRef } from 'react';
import {
  MapContainer,
  GeoJSON,
  useMap,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import type { GeoDocument } from '../../types/api';
import { getBboxFromGeometry, getCentroidFromGeometry, type Bounds } from '../../utils/geometryUtils';
import L from 'leaflet';
import OverlappingMarkerSpiderfier from '@krozamdev/overlapping-marker-spiderfier';
import { BasemapSwitcherControl } from '../map/BasemapSwitcherControl';

interface MapResultViewProps {
  results: GeoDocument[];
  highlightedResourceId?: string | null;
  /** GeoJSON string of the hovered result's locn_geometry — displayed on hover without pan/zoom */
  highlightedGeometry?: string | null;
  /** 1-based index of the first result on this page (e.g. 1 for page 1, 11 for page 2 with 10 per page) */
  resultStartIndex?: number;
}

/** Parse dcat_centroid string (e.g. "39.5,-87.43" as lat,lon) to [lat, lon] for Leaflet, or null */
function parseCentroid(centroid: string | undefined): [number, number] | null {
  if (!centroid || typeof centroid !== 'string') return null;
  const parts = centroid.split(',').map((s) => parseFloat(s.trim()));
  if (parts.length < 2 || parts.some((n) => isNaN(n))) return null;
  // Fixtures use "lat,lon"; ensure valid range (latitude -90..90, longitude -180..180)
  const [a, b] = parts;
  if (Math.abs(a) <= 90 && Math.abs(b) <= 180) return [a, b];
  if (Math.abs(b) <= 90 && Math.abs(a) <= 180) return [b, a];
  return [a, b]; // fallback: assume first is lat
}

/** Parse dcat_bbox to Leaflet bounds [[minLat, minLon], [maxLat, maxLon]]. */
function parseBbox(bbox: string | undefined): Bounds | null {
  if (!bbox || typeof bbox !== 'string') return null;
  const s = bbox.trim();

  // ENVELOPE(minX, maxX, maxY, minY)
  const envMatch = s.match(
    /ENVELOPE\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)/i
  );
  if (envMatch) {
    const minx = parseFloat(envMatch[1]);
    const maxx = parseFloat(envMatch[2]);
    const maxy = parseFloat(envMatch[3]);
    const miny = parseFloat(envMatch[4]);
    if (!isNaN(minx + maxx + maxy + miny)) {
      return [[miny, minx], [maxy, maxx]];
    }
  }

  // CSV: minX,minY,maxX,maxY
  const parts = s.split(',').map((p) => parseFloat(p.trim()));
  if (parts.length >= 4 && parts.every((n) => !isNaN(n))) {
    const [minx, miny, maxx, maxy] = parts;
    return [[miny, minx], [maxy, maxx]];
  }

  return null;
}

// Controller: fit map to union of result bboxes when results change
const MapInitialFitController: React.FC<{
  bounds: Bounds[];
}> = ({ bounds }) => {
  const map = useMap();

  useEffect(() => {
    if (bounds.length === 0) return;
    const valid = bounds.filter(
      ([[minLat, minLon], [maxLat, maxLon]]) =>
        !isNaN(minLat + minLon + maxLat + maxLon) &&
        minLat >= -90 && maxLat <= 90 &&
        minLon >= -180 && maxLon <= 180
    );
    if (valid.length === 0) return;
    const group = L.featureGroup(
      valid.map((b) => L.rectangle(b))
    );
    if (group.getBounds().isValid()) {
      map.flyToBounds(group.getBounds(), { padding: [50, 50], duration: 0.5 });
    }
  }, [bounds, map]);

  return null;
};

/** Create a numbered pin icon (circle with number inside) */
function createNumberedPinIcon(
  resultNumber: number,
  isHighlighted: boolean
): L.DivIcon {
  const color = isHighlighted ? '#f59e0b' : '#6366f1';
  const size = isHighlighted ? 28 : 24;
  return L.divIcon({
    html: `<span style="
      display: flex; align-items: center; justify-content: center;
      width: ${size}px; height: ${size}px;
      border-radius: 50%;
      background: ${color};
      color: white;
      font-size: ${isHighlighted ? 12 : 11}px;
      font-weight: 600;
      border: 2px solid white;
      box-shadow: 0 1px 3px rgba(0,0,0,0.3);
    ">${resultNumber}</span>`,
    className: 'numbered-pin-icon',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

/** Entry for each marker so we can update icon/z-index on highlight */
interface MarkerEntry {
  marker: L.Marker;
  resourceId: string;
  resultNumber: number;
}

/** Renders numbered markers with OverlappingMarkerSpiderfier for overlapping pins */
const SpiderfiedMarkers: React.FC<{
  pins: { resource: GeoDocument; position: [number, number]; resultNumber: number }[];
  highlightedResourceId: string | null;
}> = ({ pins, highlightedResourceId }) => {
  const map = useMap();
  const omsRef = useRef<InstanceType<typeof OverlappingMarkerSpiderfier> | null>(null);
  const entriesRef = useRef<MarkerEntry[]>([]);

  useEffect(() => {
    if (!map || pins.length === 0) return;

    const oms = new OverlappingMarkerSpiderfier(map, {
      nearbyDistance: 30,
      circleSpiralSwitchover: 9,
    });
    omsRef.current = oms;

    const popup = L.popup();
    oms.addListener('click', (marker: L.Marker & { _popupContent?: HTMLElement }) => {
      if (marker._popupContent) {
        popup.setContent(marker._popupContent);
        popup.setLatLng(marker.getLatLng());
        map.openPopup(popup);
      }
    });

    const entries: MarkerEntry[] = [];
    pins.forEach((p) => {
      const marker = L.marker(p.position, {
        icon: createNumberedPinIcon(p.resultNumber, false),
      });
      const container = document.createElement('div');
      container.className = 'text-xs min-w-[200px]';
      container.innerHTML = `
        <span class="text-slate-500 text-xs block mb-1">Result ${p.resultNumber}</span>
        <strong class="block mb-1 text-sm">${escapeHtml(p.resource.attributes.ogm.dct_title_s || '(Untitled)')}</strong>
        <span class="text-slate-500 block mb-2">${escapeHtml(p.resource.id)}</span>
        <a href="/resources/${escapeHtml(p.resource.id)}" class="text-indigo-600 hover:text-indigo-800 font-medium hover:underline">View Details</a>
      `;
      (marker as L.Marker & { _popupContent?: HTMLElement })._popupContent = container;
      marker.addTo(map);
      oms.addMarker(marker);
      entries.push({ marker, resourceId: p.resource.id, resultNumber: p.resultNumber });
    });
    entriesRef.current = entries;

    return () => {
      const oms = omsRef.current;
      if (oms) {
        oms.clearMarkers();
        oms.unspiderfy();
        entriesRef.current.forEach((e) => map.removeLayer(e.marker));
        omsRef.current = null;
        entriesRef.current = [];
      }
    };
  }, [map, pins]);

  // Update pin color and z-index when highlighted result changes
  useEffect(() => {
    const entries = entriesRef.current;
    if (entries.length === 0) return;

    const HIGH_Z = 10000;
    entries.forEach(({ marker, resourceId, resultNumber }) => {
      const isHighlighted = resourceId === highlightedResourceId;
      marker.setIcon(createNumberedPinIcon(resultNumber, isHighlighted));
      marker.setZIndexOffset(isHighlighted ? HIGH_Z : 0);
    });
  }, [highlightedResourceId]);

  return null;
};

function escapeHtml(s: string): string {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

export const MapResultView: React.FC<MapResultViewProps> = ({
  results,
  highlightedResourceId,
  highlightedGeometry,
  resultStartIndex = 1,
}) => {
  // Pin each result at its centroid (or geometry-derived centroid when dcat_centroid missing)
  const pins = useMemo(
    () =>
      results
        .map((r, idx) => {
          const centroid =
            r.attributes?.ogm?.dcat_centroid ??
            r.attributes?.ogm?.dcat_centroid_original;
          let pos = parseCentroid(centroid);
          if (!pos) {
            const geom =
              r.meta?.ui?.viewer?.geometry ??
              r.attributes?.ogm?.locn_geometry ??
              r.attributes?.ogm?.locn_geometry_original;
            pos = getCentroidFromGeometry(geom ?? undefined) ?? null;
          }
          if (!pos) return null;
          return {
            resource: r,
            position: pos as [number, number],
            resultNumber: resultStartIndex + idx,
          };
        })
        .filter((f) => f !== null) as {
        resource: GeoDocument;
        position: [number, number];
        resultNumber: number;
      }[],
    [results, resultStartIndex]
  );

  // Fit map to union of result bboxes (not centroids) so full extent is visible
  const allBounds = useMemo(() => {
    const out: Bounds[] = [];
    for (const r of results) {
      const ogm = r.attributes?.ogm;
      let b = parseBbox(ogm?.dcat_bbox ?? ogm?.dcat_bbox_original);
      if (!b) {
        const geom =
          r.meta?.ui?.viewer?.geometry ??
          ogm?.locn_geometry ??
          ogm?.locn_geometry_original;
        b = getBboxFromGeometry(geom ?? undefined) ?? null;
      }
      if (!b) {
        const centroid =
          ogm?.dcat_centroid ?? ogm?.dcat_centroid_original;
        let pos = parseCentroid(centroid);
        if (!pos) {
          const geom =
            r.meta?.ui?.viewer?.geometry ??
            ogm?.locn_geometry ??
            ogm?.locn_geometry_original;
          pos = getCentroidFromGeometry(geom ?? undefined) ?? null;
        }
        if (pos) {
          const [lat, lon] = pos;
          const ε = 0.01;
          b = [[lat - ε, lon - ε], [lat + ε, lon + ε]];
        }
      }
      if (b) out.push(b);
    }
    return out;
  }, [results]);

  const highlightedGeoJson = useMemo(() => {
    if (!highlightedGeometry || typeof highlightedGeometry !== 'string') return null;
    try {
      const parsed = JSON.parse(highlightedGeometry);
      // GeoJSON component expects Feature, FeatureCollection, or raw geometry
      return parsed as GeoJSON.Feature | GeoJSON.FeatureCollection | GeoJSON.Geometry;
    } catch {
      return null;
    }
  }, [highlightedGeometry]);

  if (pins.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center text-slate-500 bg-gray-50 dark:bg-slate-900">
        No mappable results found in this page.
      </div>
    );
  }

  return (
    <div className="h-full w-full bg-slate-100 rounded-lg overflow-hidden relative z-0">
      <style>{`.numbered-pin-icon { background: transparent !important; border: none !important; }`}</style>
      <MapContainer
        center={[0, 0]}
        zoom={2}
        className="h-full w-full"
        scrollWheelZoom={true}
      >
        <BasemapSwitcherControl />

        {/* Numbered centroid pins with spiderfier for overlapping markers */}
        <SpiderfiedMarkers
          pins={pins}
          highlightedResourceId={highlightedResourceId ?? null}
        />

        {/* Hover overlay: show complex locn_geometry on hover — no pan/zoom */}
        {highlightedGeoJson && (
          <GeoJSON
            key={highlightedResourceId ?? 'hover'}
            data={highlightedGeoJson}
            style={{
              color: '#f59e0b',
              weight: 3,
              opacity: 1,
              fillOpacity: 0.25,
              fillColor: '#f59e0b',
            }}
          />
        )}

        <MapInitialFitController bounds={allBounds} />
      </MapContainer>
    </div>
  );
};

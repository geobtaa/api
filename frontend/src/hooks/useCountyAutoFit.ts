import { useEffect } from 'react';
import type * as Leaflet from 'leaflet';
import {
  stateAbbrToFips,
  parseCountyFacetValue,
  normalizeName,
} from '../utils/geoCounty';
import type { GeoJsonData, GeoJsonFeature } from '../types/map';

interface Params {
  map: Leaflet.Map;
  geoJson: GeoJsonData | null;
  countyItems: Array<{ attributes: { value: string; hits: number } }>;
  searchQuery: string;
}

// Auto-pans the county map:
// - No query: default US view (consistent with other maps)
// - With query: zooms to the top-hit county (by facet hits) for a closer view
export function useCountyAutoFit({
  map,
  geoJson,
  countyItems,
  searchQuery,
}: Params) {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!geoJson || !geoJson.features || !Array.isArray(countyItems)) return;

    // If no search query, keep default US-focused view
    if (!searchQuery || searchQuery.trim() === '') {
      map.setView([39.8283, -98.5795], 3);
      return;
    }

    // Find top county by hits and compute bounds from GeoJSON
    const topCountyItem = countyItems.reduce(
      (max, item) =>
        (item.attributes.hits || 0) > (max?.attributes.hits || 0) ? item : max,
      countyItems[0]
    );
    if (!topCountyItem) return;

    const { stateAbbr, countyName } = parseCountyFacetValue(
      topCountyItem.attributes.value
    );
    const targetStateFips = stateAbbrToFips[stateAbbr];
    if (!targetStateFips || !countyName) return;

    const targetCountyNorm = normalizeName(countyName);

    try {
      // Filter GeoJSON to the specific county feature
      void (async () => {
        const mod = await import('leaflet');
        const L = mod.default;

        const layer = L.geoJSON(geoJson as GeoJsonData, {
          filter: (feature: GeoJsonFeature) => {
            const featureStateFips = (
              feature?.properties?.STATE ||
              feature?.properties?.STATEFP ||
              ''
            )
              .toString()
              .padStart(2, '0');
            const featureCountyNameRaw =
              feature?.properties?.NAME ||
              feature?.properties?.name ||
              feature?.properties?.county ||
              '';
            const featureCountyNorm = normalizeName(featureCountyNameRaw);
            return (
              featureStateFips === targetStateFips &&
              featureCountyNorm === targetCountyNorm
            );
          },
        });

        const bounds = layer.getBounds();
        if (bounds && bounds.isValid()) {
          // Pull in closer than state bounds; cap zoom to avoid over-zooming small counties
          map.fitBounds(bounds, { padding: [20, 20], maxZoom: 7 });
        }

        layer.remove();
      })();
    } catch {
      // no-op: on failure, keep existing view
    }
  }, [map, geoJson, countyItems, searchQuery]);
}

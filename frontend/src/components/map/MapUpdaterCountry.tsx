import { useEffect, useState } from 'react';
import { GeoJSON } from 'react-leaflet';
import type {
  ChoroplethData,
  GeoJsonData,
  MapFeatureClickPayload,
} from '../../types/map';
import { fetchGeoJsonForLevel } from '../../services/geojson';
import { formatCount } from '../../utils/formatNumber';

// Normalize for loose matching between API labels and GeoJSON names
function normalizeName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z\s]/g, '')
    .trim();
}

// Color scale used across maps
function getColor(intensity: number): string {
  return intensity > 0.8
    ? '#800026'
    : intensity > 0.6
      ? '#BD0026'
      : intensity > 0.4
        ? '#E31A1C'
        : intensity > 0.2
          ? '#FC4E2A'
          : intensity > 0.1
            ? '#FD8D3C'
            : intensity > 0
              ? '#FEB24C'
              : '#FED976';
}

export function MapUpdaterCountry({
  data,
  onFeatureClick,
}: {
  data: ChoroplethData;
  onFeatureClick: (feature: MapFeatureClickPayload) => void;
}) {
  // GeoJSON is loaded per-zoom-level to keep code small and responsibilities clear
  const [geoJson, setGeoJson] = useState<GeoJsonData | null>(null);

  useEffect(() => {
    fetchGeoJsonForLevel('country')
      .then(setGeoJson)
      .catch(() => setGeoJson(null));
  }, []);

  // Precompute scale for choropleth intensity
  const currentData = data.country;
  const maxHits = Math.max(...currentData.map((d) => d.attributes.hits), 1);

  if (!geoJson || !geoJson.features) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-sm text-gray-600">Loading country boundaries...</p>
        </div>
      </div>
    );
  }

  // Map API facet label to GeoJSON feature name for hit lookup
  const getHits = (featureName: string) => {
    const item = currentData.find((dataItem) => {
      const dataLabel = dataItem.attributes.label.toLowerCase();
      const geoName = featureName.toLowerCase();
      if (dataLabel === geoName) return true;
      const nd = normalizeName(dataLabel);
      const ng = normalizeName(geoName);
      return (
        nd === ng ||
        (nd.includes('united states') &&
          (ng.includes('united states') || ng === 'us' || ng === 'usa')) ||
        (nd.includes('usa') &&
          (ng.includes('usa') || ng === 'us' || ng.includes('united states')))
      );
    });
    return item ? item.attributes.hits : 0;
  };

  // Render GeoJSON and wire style and popups
  return (
    <GeoJSON
      data={geoJson}
      style={(feature) => {
        const featureName =
          feature?.properties?.name ||
          feature?.properties?.NAME ||
          feature?.properties?.ADMIN ||
          'Unknown Country';
        const hits = getHits(featureName);
        const intensity = hits / maxHits;
        return {
          fillColor: getColor(intensity),
          weight: 2,
          opacity: 1,
          color: 'white',
          dashArray: '3',
          fillOpacity: 0.7,
        };
      }}
      onEachFeature={(feature, layer) => {
        const featureName =
          feature?.properties?.name ||
          feature?.properties?.NAME ||
          'Unknown Country';
        const hits = getHits(featureName);
        layer.bindPopup(`
          <div>
            <h3>${featureName}</h3>
            <p><strong>Resources:</strong> ${formatCount(hits)}</p>
            <p><strong>Level:</strong> country</p>
          </div>
        `);
        layer.on('click', () =>
          onFeatureClick({ properties: { name: featureName, hits } })
        );
      }}
    />
  );
}

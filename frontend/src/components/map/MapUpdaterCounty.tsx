import { useEffect, useState } from 'react';
import { GeoJSON, useMap } from 'react-leaflet';
import type {
  ChoroplethData,
  GeoJsonData,
  MapFeatureClickPayload,
} from '../../types/map';
import { fetchGeoJsonForLevel } from '../../services/geojson';
import { getCountyHitsFromFeature } from '../../utils/geoCounty';
import { useCountyAutoFit } from '../../hooks/useCountyAutoFit';
import { formatCount } from '../../utils/formatNumber';

// Shared color scale
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

export function MapUpdaterCounty({
  data,
  onFeatureClick,
  searchQuery,
}: {
  data: ChoroplethData;
  onFeatureClick: (feature: MapFeatureClickPayload) => void;
  searchQuery: string;
}) {
  const map = useMap();
  // Load county GeoJSON (FIPS-coded) locally
  const [geoJson, setGeoJson] = useState<GeoJsonData | null>(null);

  useEffect(() => {
    fetchGeoJsonForLevel('county')
      .then(setGeoJson)
      .catch(() => setGeoJson(null));
  }, []);

  // Auto-pan/zoom: without query -> default US; with query -> top county bounds
  useCountyAutoFit({ map, geoJson, countyItems: data.county, searchQuery });

  // Precompute scale for choropleth intensity
  const currentData = data.county;
  const maxHits = Math.max(...currentData.map((d) => d.attributes.hits), 1);

  if (!geoJson || !geoJson.features) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-sm text-gray-600">Loading county boundaries...</p>
        </div>
      </div>
    );
  }

  // Render GeoJSON, match each county using (state FIPS + normalized county name) against facet value (WOF-derived)
  return (
    <GeoJSON
      data={geoJson}
      style={(feature) => {
        const hits = getCountyHitsFromFeature(feature, data.county);
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
        const name =
          feature?.properties?.NAME ||
          feature?.properties?.name ||
          feature?.properties?.county ||
          'Unknown County';
        const hits = getCountyHitsFromFeature(feature, data.county);
        layer.bindPopup(`
          <div>
            <h3>${name}</h3>
            <p><strong>Resources:</strong> ${formatCount(hits)}</p>
            <p><strong>Level:</strong> county</p>
          </div>
        `);
        layer.on('click', () => onFeatureClick({ properties: { name, hits } }));
      }}
    />
  );
}

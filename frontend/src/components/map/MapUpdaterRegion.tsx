import { useEffect, useState } from 'react';
import { GeoJSON } from 'react-leaflet';
import type {
  ChoroplethData,
  GeoJsonData,
  MapFeatureClickPayload,
} from '../../types/map';
import { fetchGeoJsonForLevel } from '../../services/geojson';
import { formatCount } from '../../utils/formatNumber';

// Color scale shared with other updaters
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

export function MapUpdaterRegion({
  data,
  onFeatureClick,
}: {
  data: ChoroplethData;
  onFeatureClick: (feature: MapFeatureClickPayload) => void;
}) {
  // Load US states GeoJSON and keep local
  const [geoJson, setGeoJson] = useState<GeoJsonData | null>(null);

  useEffect(() => {
    fetchGeoJsonForLevel('region')
      .then(setGeoJson)
      .catch(() => setGeoJson(null));
  }, []);

  // Precompute scale for choropleth intensity
  const currentData = data.region;
  const maxHits = Math.max(...currentData.map((d) => d.attributes.hits), 1);

  if (!geoJson || !geoJson.features) {
    return (
      <div className="h-full flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <p className="text-sm text-gray-600">Loading state boundaries...</p>
        </div>
      </div>
    );
  }

  // Map API facet label to state feature name (simple partial match)
  const getHits = (featureName: string) => {
    const dataItem = currentData.find((d) => {
      const label = d.attributes.label.toLowerCase();
      const geo = featureName.toLowerCase();
      return label === geo || label.includes(geo) || geo.includes(label);
    });
    return dataItem ? dataItem.attributes.hits : 0;
  };

  // Render GeoJSON and wire style and popups
  return (
    <GeoJSON
      data={geoJson}
      style={(feature) => {
        const featureName =
          feature?.properties?.name ||
          feature?.properties?.NAME ||
          feature?.properties?.state ||
          'Unknown State';
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
          'Unknown State';
        const hits = getHits(featureName);
        layer.bindPopup(`
          <div>
            <h3>${featureName}</h3>
            <p><strong>Resources:</strong> ${formatCount(hits)}</p>
            <p><strong>Level:</strong> region</p>
          </div>
        `);
        layer.on('click', () =>
          onFeatureClick({ properties: { name: featureName, hits } })
        );
      }}
    />
  );
}

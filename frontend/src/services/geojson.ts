// Service: fetch GeoJSON for a given zoom level (country/region/county)
// Keeps MapUpdater components slim and centralizes URL selection
import type { ZoomLevel, GeoJsonData } from '../types/map';

export async function fetchGeoJsonForLevel(
  level: ZoomLevel
): Promise<GeoJsonData> {
  let geoJsonUrl: string;
  switch (level) {
    case 'country':
      geoJsonUrl =
        'https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson';
      break;
    case 'region':
      geoJsonUrl =
        'https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json';
      break;
    case 'county':
      geoJsonUrl =
        'https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json';
      break;
    default:
      geoJsonUrl =
        'https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json';
  }

  const response = await fetch(geoJsonUrl);
  if (!response.ok) {
    throw new Error(`Failed to fetch GeoJSON: ${response.status}`);
  }
  return response.json();
}

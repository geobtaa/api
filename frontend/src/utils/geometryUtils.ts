/**
 * Utility functions for handling geometry data formats
 */

/**
 * Converts WKT (Well-Known Text) to GeoJSON format
 * @param wkt - WKT string (e.g., "POLYGON((-96.796 48.756, -90.379 48.756, -90.379 43.429, -96.796 43.429, -96.796 48.756))")
 * @returns GeoJSON object or null if parsing fails
 */
export function wktToGeoJSON(
  wkt: string
): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  try {
    // Remove extra whitespace and normalize
    const cleanWkt = wkt.trim().replace(/\s+/g, ' ');

    // Check if it's a MULTIPOLYGON
    if (cleanWkt.toUpperCase().startsWith('MULTIPOLYGON')) {
      return parseMultiPolygon(cleanWkt);
    }

    // Check if it's a POLYGON
    if (cleanWkt.toUpperCase().startsWith('POLYGON')) {
      return parsePolygon(cleanWkt);
    }

    console.warn('WKT is not a POLYGON or MULTIPOLYGON:', wkt);
    return null;
  } catch (error) {
    console.error('Error parsing WKT to GeoJSON:', error);
    return null;
  }
}

/**
 * Parse a single POLYGON from WKT
 */
function parsePolygon(wkt: string): GeoJSON.Polygon | null {
  // Extract coordinates from POLYGON((...))
  const match = wkt.match(/POLYGON\s*\(\s*\(\s*(.+?)\s*\)\s*\)/i);
  if (!match) {
    console.warn('Could not parse WKT coordinates:', wkt);
    return null;
  }

  // Parse coordinate pairs
  const coordString = match[1];
  const coordPairs = coordString.split(',').map((pair) => {
    const [lon, lat] = pair.trim().split(/\s+/).map(Number);
    return [lon, lat]; // Return [lon, lat] for standard GeoJSON format
  });

  // Validate coordinates
  if (coordPairs.length < 3) {
    console.warn('Invalid polygon: need at least 3 points');
    return null;
  }

  // Ensure first and last points are the same (closed polygon)
  const firstPoint = coordPairs[0];
  const lastPoint = coordPairs[coordPairs.length - 1];
  if (firstPoint[0] !== lastPoint[0] || firstPoint[1] !== lastPoint[1]) {
    coordPairs.push([...firstPoint]); // Close the polygon
  }

  return {
    type: 'Polygon',
    coordinates: [coordPairs],
  };
}

/**
 * Parse a MULTIPOLYGON from WKT
 */
function parseMultiPolygon(wkt: string): GeoJSON.MultiPolygon | null {
  // Extract all polygon coordinate strings from MULTIPOLYGON(((...)),((...)),...)
  const match = wkt.match(/MULTIPOLYGON\s*\(\s*(.+)\s*\)/i);
  if (!match) {
    console.warn('Could not parse MULTIPOLYGON coordinates:', wkt);
    return null;
  }

  const polygonsString = match[1];
  const polygons: number[][][] = [];

  // More robust splitting - look for the pattern of closing and opening parentheses
  // Split on ")),((" to separate individual polygons
  const polygonStrings = polygonsString.split(/\)\s*,\s*\(/);

  for (let i = 0; i < polygonStrings.length; i++) {
    let polygonString = polygonStrings[i];

    // Clean up the polygon string - remove leading/trailing parentheses
    polygonString = polygonString.replace(/^\(\s*/, '').replace(/\s*\)$/, '');

    // Parse coordinate pairs for this polygon
    const coordPairs = polygonString
      .split(',')
      .map((pair) => {
        const trimmedPair = pair.trim();

        // Remove any remaining parentheses from individual coordinate pairs
        const cleanPair = trimmedPair.replace(/^\(/, '').replace(/\)$/, '');
        const coords = cleanPair.split(/\s+/);

        if (coords.length !== 2) {
          console.warn(
            'Invalid coordinate pair:',
            cleanPair,
            'split into:',
            coords
          );
          return null;
        }

        const lon = parseFloat(coords[0]);
        const lat = parseFloat(coords[1]);

        // Validate that we got valid numbers
        if (isNaN(lon) || isNaN(lat)) {
          console.warn(
            'Invalid coordinate values:',
            coords,
            'from pair:',
            cleanPair
          );
          return null;
        }

        // Return [lon, lat] for standard GeoJSON format
        return [lon, lat];
      })
      .filter((coord): coord is [number, number] => coord !== null);

    // Validate coordinates
    if (coordPairs.length < 3) {
      console.warn(
        'Invalid polygon in MULTIPOLYGON: need at least 3 points, got',
        coordPairs.length
      );
      continue;
    }

    // Ensure first and last points are the same (closed polygon)
    const firstPoint = coordPairs[0];
    const lastPoint = coordPairs[coordPairs.length - 1];
    if (firstPoint[0] !== lastPoint[0] || firstPoint[1] !== lastPoint[1]) {
      coordPairs.push([...firstPoint]); // Close the polygon
    }

    polygons.push(coordPairs);
  }

  if (polygons.length === 0) {
    console.warn('No valid polygons found in MULTIPOLYGON');
    return null;
  }

  return {
    type: 'MultiPolygon' as const,
    coordinates: polygons,
  };
}

/**
 * Converts various geometry formats to GeoJSON
 * @param geometry - Geometry data in various formats
 * @returns GeoJSON object or null if conversion fails
 */
export function normalizeGeometry(
  geometry:
    | string
    | GeoJSON.Polygon
    | GeoJSON.MultiPolygon
    | { wkt: string }
    | null
): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  if (!geometry) return null;

  // If it's already GeoJSON
  if (
    typeof geometry === 'object' &&
    'type' in geometry &&
    'coordinates' in geometry
  ) {
    return geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon;
  }

  // If it's a WKT string
  if (typeof geometry === 'string') {
    return wktToGeoJSON(geometry);
  }

  // If it's a parsed object with WKT-like structure
  if (typeof geometry === 'object' && 'wkt' in geometry) {
    return wktToGeoJSON((geometry as { wkt: string }).wkt);
  }

  console.warn('Unknown geometry format:', geometry);
  return null;
}

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

/** GeoJSON geometry with coordinates (Point, Polygon, MultiPolygon, LineString, etc.) */
type GeoJsonGeometry =
  | GeoJSON.Point
  | GeoJSON.Polygon
  | GeoJSON.MultiPolygon
  | GeoJSON.LineString
  | GeoJSON.MultiPoint
  | GeoJSON.MultiLineString;

function collectLonLatPairs(geom: GeoJsonGeometry): [number, number][] {
  const coords = geom.coordinates;
  if (!coords || !Array.isArray(coords)) return [];

  const type = (geom.type || '').toLowerCase();
  if (type === 'point') {
    const c = coords as number[];
    if (c.length >= 2 && typeof c[0] === 'number' && typeof c[1] === 'number') {
      return [[c[0], c[1]]];
    }
    return [];
  }
  if (type === 'linestring' || type === 'multipoint') {
    return (coords as number[][]).filter(
      (c): c is [number, number] =>
        Array.isArray(c) && c.length >= 2 && typeof c[0] === 'number' && typeof c[1] === 'number'
    );
  }
  if (type === 'polygon') {
    const rings = coords as number[][][];
    const firstRing = rings[0];
    return Array.isArray(firstRing)
      ? firstRing.filter(
          (c): c is [number, number] =>
            Array.isArray(c) && c.length >= 2 && typeof c[0] === 'number' && typeof c[1] === 'number'
        )
      : [];
  }
  if (type === 'multipolygon' || type === 'multilinestring') {
    const parts = coords as number[][][];
    return parts.flatMap((part) =>
      Array.isArray(part)
        ? part.filter(
            (c): c is [number, number] =>
              Array.isArray(c) && c.length >= 2 && typeof c[0] === 'number' && typeof c[1] === 'number'
          )
        : []
    );
  }
  return [];
}

/**
 * Compute centroid [lat, lon] from geometry (bbox center for non-points).
 * Use when dcat_centroid is missing but locn_geometry or meta.ui.viewer.geometry exists.
 */
export function getCentroidFromGeometry(
  geometry:
    | string
    | GeoJsonGeometry
    | { type: string; coordinates: unknown }
    | null
    | undefined
): [number, number] | null {
  if (!geometry) return null;

  let geom: GeoJsonGeometry | null = null;

  if (typeof geometry === 'object' && geometry !== null && 'type' in geometry && 'coordinates' in geometry) {
    geom = geometry as GeoJsonGeometry;
  } else if (typeof geometry === 'string') {
    const s = geometry.trim();
    if (s.startsWith('{')) {
      try {
        const parsed = JSON.parse(s) as { type?: string; coordinates?: unknown };
        if (parsed && parsed.type && parsed.coordinates) {
          geom = parsed as GeoJsonGeometry;
        }
      } catch {
        // not JSON
      }
    }
    if (!geom && /^ENVELOPE\s*\(/i.test(s)) {
      const match = s.match(
        /ENVELOPE\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)/i
      );
      if (match) {
        const minx = parseFloat(match[1]);
        const maxx = parseFloat(match[2]);
        const maxy = parseFloat(match[3]);
        const miny = parseFloat(match[4]);
        if (!isNaN(minx + maxx + maxy + miny)) {
          const lon = (minx + maxx) / 2;
          const lat = (miny + maxy) / 2;
          return [lat, lon];
        }
      }
    }
    if (!geom && (s.toUpperCase().startsWith('POLYGON') || s.toUpperCase().startsWith('MULTIPOLYGON'))) {
      const normalized = normalizeGeometry(s);
      if (normalized) geom = normalized as GeoJsonGeometry;
    }
  }

  if (!geom) return null;

  const pairs = collectLonLatPairs(geom);
  if (pairs.length === 0) return null;

  const lons = pairs.map(([lon]) => lon);
  const lats = pairs.map(([, lat]) => lat);
  const lon = (Math.min(...lons) + Math.max(...lons)) / 2;
  const lat = (Math.min(...lats) + Math.max(...lats)) / 2;

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;

  return [lat, lon];
}

/**
 * Bounds as [[minLat, minLon], [maxLat, maxLon]] (Leaflet format).
 */
export type Bounds = [[number, number], [number, number]];

/**
 * Compute bbox [[minLat, minLon], [maxLat, maxLon]] from geometry.
 * Use for map fit-to-bounds when dcat_bbox is missing but locn_geometry exists.
 */
export function getBboxFromGeometry(
  geometry:
    | string
    | GeoJsonGeometry
    | { type: string; coordinates: unknown }
    | null
    | undefined
): Bounds | null {
  if (!geometry) return null;

  let geom: GeoJsonGeometry | null = null;

  if (typeof geometry === 'object' && geometry !== null && 'type' in geometry && 'coordinates' in geometry) {
    geom = geometry as GeoJsonGeometry;
  } else if (typeof geometry === 'string') {
    const s = geometry.trim();
    if (s.startsWith('{')) {
      try {
        const parsed = JSON.parse(s) as { type?: string; coordinates?: unknown };
        if (parsed && parsed.type && parsed.coordinates) {
          geom = parsed as GeoJsonGeometry;
        }
      } catch {
        // not JSON
      }
    }
    if (!geom && /^ENVELOPE\s*\(/i.test(s)) {
      const match = s.match(
        /ENVELOPE\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)/i
      );
      if (match) {
        const minx = parseFloat(match[1]);
        const maxx = parseFloat(match[2]);
        const maxy = parseFloat(match[3]);
        const miny = parseFloat(match[4]);
        if (!isNaN(minx + maxx + maxy + miny)) {
          return [[miny, minx], [maxy, maxx]];
        }
      }
    }
    if (!geom && (s.toUpperCase().startsWith('POLYGON') || s.toUpperCase().startsWith('MULTIPOLYGON'))) {
      const normalized = normalizeGeometry(s);
      if (normalized) geom = normalized as GeoJsonGeometry;
    }
  }

  if (!geom) return null;

  const pairs = collectLonLatPairs(geom);
  if (pairs.length === 0) return null;

  const lons = pairs.map(([lon]) => lon);
  const lats = pairs.map(([, lat]) => lat);
  let minLon = Math.min(...lons);
  let maxLon = Math.max(...lons);
  let minLat = Math.min(...lats);
  let maxLat = Math.max(...lats);

  // For point geometries, add small buffer so bounds are non-degenerate
  if (minLat === maxLat && minLon === maxLon) {
    const ε = 0.001;
    minLat -= ε;
    maxLat += ε;
    minLon -= ε;
    maxLon += ε;
  }

  if (!Number.isFinite(minLat) || !Number.isFinite(maxLat) || !Number.isFinite(minLon) || !Number.isFinite(maxLon)) return null;
  if (minLat < -90 || maxLat > 90 || minLon < -180 || maxLon > 180) return null;

  return [[minLat, minLon], [maxLat, maxLon]];
}

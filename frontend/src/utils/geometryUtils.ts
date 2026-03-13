/**
 * Utility functions for handling geometry data formats
 */

/**
 * Converts WKT (Well-Known Text) to GeoJSON format
 * @param wkt - WKT string (e.g., "POLYGON((-96.796 48.756, -90.379 48.756, -90.379 43.429, -96.796 43.429, -96.796 48.756))")
 * @returns GeoJSON object or null if parsing fails
 */
/**
 * Parse ENVELOPE(minx, maxx, maxy, miny) WKT to GeoJSON Polygon.
 * ENVELOPE format: west, east, north, south (lon, lon, lat, lat).
 */
function parseEnvelope(wkt: string): GeoJSON.Polygon | null {
  const match = wkt.match(
    /ENVELOPE\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)/i
  );
  if (!match) return null;
  const minx = parseFloat(match[1]);
  const maxx = parseFloat(match[2]);
  const maxy = parseFloat(match[3]);
  const miny = parseFloat(match[4]);
  if (Number.isNaN(minx + maxx + maxy + miny)) return null;
  // GeoJSON polygon ring: [minx,maxy], [maxx,maxy], [maxx,miny], [minx,miny], [minx,maxy]
  const ring: [number, number][] = [
    [minx, maxy],
    [maxx, maxy],
    [maxx, miny],
    [minx, miny],
    [minx, maxy],
  ];
  return { type: 'Polygon', coordinates: [ring] };
}

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

    // Check if it's an ENVELOPE (bbox in WKT form)
    if (cleanWkt.toUpperCase().startsWith('ENVELOPE')) {
      return parseEnvelope(cleanWkt);
    }

    console.warn('WKT is not a POLYGON, MULTIPOLYGON, or ENVELOPE:', wkt);
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

  // GeoJSON MultiPolygon: each polygon is [ring1, hole?, ...], wrap each ring
  return {
    type: 'MultiPolygon' as const,
    coordinates: polygons.map((ring) => [ring]),
  };
}

/**
 * Converts various geometry formats to GeoJSON Polygon/MultiPolygon.
 * Same logic used by LocationMap on the resource page.
 * @param geometry - Geometry data in various formats
 * @returns GeoJSON object or null if conversion fails
 */
export function normalizeGeometry(
  geometry:
    | string
    | GeoJSON.Polygon
    | GeoJSON.MultiPolygon
    | GeoJSON.Feature
    | { wkt: string; type?: string; geometry?: unknown; coordinates?: unknown }
    | null
): GeoJSON.Polygon | GeoJSON.MultiPolygon | null {
  if (!geometry) return null;

  // GeoJSON Feature: extract nested geometry
  if (typeof geometry === 'object' && (geometry as { type?: string }).type === 'Feature') {
    const geom = (geometry as GeoJSON.Feature).geometry;
    return geom ? normalizeGeometry(geom) : null;
  }

  // If it's already GeoJSON with coordinates
  if (
    typeof geometry === 'object' &&
    'type' in geometry &&
    'coordinates' in geometry
  ) {
    return geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon;
  }

  // If it's a WKT string
  if (typeof geometry === 'string') {
    const s = geometry.trim();
    if (s.startsWith('{')) {
      try {
        const parsed = JSON.parse(s) as { type?: string; geometry?: unknown; coordinates?: unknown };
        return normalizeGeometry(parsed);
      } catch {
        // Not valid JSON, try as WKT
      }
    }
    return wktToGeoJSON(geometry);
  }

  // If it's a parsed object with WKT-like structure
  if (typeof geometry === 'object' && 'wkt' in geometry) {
    return wktToGeoJSON((geometry as { wkt: string }).wkt);
  }

  console.warn('Unknown geometry format:', geometry);
  return null;
}

/**
 * Convert normalized geometry to Leaflet GeoJSON features (same format as LocationMap).
 * Use this for search hover overlay so we match resource page behavior exactly.
 */
export function geometryToLeafletFeatures(
  normalized: GeoJSON.Polygon | GeoJSON.MultiPolygon | null
): GeoJSON.Feature[] {
  if (!normalized) return [];
  if (normalized.type === 'MultiPolygon') {
    return normalized.coordinates.map((polygonRings) => ({
      type: 'Feature' as const,
      geometry: {
        type: 'Polygon' as const,
        coordinates: polygonRings, // polygonRings is [exterior, hole1, ...]
      },
      properties: {},
    }));
  }
  return [
    {
      type: 'Feature' as const,
      geometry: normalized,
      properties: {},
    },
  ];
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
  if (type === 'multipolygon') {
    const parts = coords as number[][][][];
    return parts.flatMap((polygon) =>
      Array.isArray(polygon)
        ? polygon.flatMap((ring) =>
            Array.isArray(ring)
              ? ring.filter(
                  (c): c is [number, number] =>
                    Array.isArray(c) &&
                    c.length >= 2 &&
                    typeof c[0] === 'number' &&
                    typeof c[1] === 'number'
                )
              : []
          )
        : []
    );
  }
  if (type === 'multilinestring') {
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

/**
 * WGS84 extent as [minLon, minLat, maxLon, maxLat] for OpenLayers view.fit().
 * Used by ResourceViewer to pan/zoom COG/PMTiles map to the correct location.
 */
export type Wgs84Extent = [number, number, number, number];

/**
 * Extract WGS84 extent [minLon, minLat, maxLon, maxLat] from viewer geometry.
 * Handles GeoJSON Feature (with geometry), raw Polygon, and FeatureCollection.
 * Returns null if geometry is invalid or cannot be parsed.
 */
export function getWgs84ExtentFromViewerGeometry(
  geometryForViewer: string | null | undefined
): Wgs84Extent | null {
  if (!geometryForViewer || typeof geometryForViewer !== 'string') return null;
  try {
    const geom = JSON.parse(geometryForViewer) as Record<string, unknown>;
    const poly =
      (geom.geometry as { coordinates?: unknown[] } | undefined) ??
      (geom.type === 'Polygon' ? (geom as { coordinates?: unknown[] }) : null);
    const coords = poly?.coordinates?.[0];
    if (!coords || !Array.isArray(coords)) return null;
    const lons = coords.map((c: unknown) =>
      Array.isArray(c) ? (c as number[])[0] : NaN
    );
    const lats = coords.map((c: unknown) =>
      Array.isArray(c) ? (c as number[])[1] : NaN
    );
    const minX = Math.min(...lons);
    const minY = Math.min(...lats);
    const maxX = Math.max(...lons);
    const maxY = Math.max(...lats);
    if (!Number.isFinite(minX + minY + maxX + maxY)) return null;
    return [minX, minY, maxX, maxY];
  } catch {
    return null;
  }
}

/**
 * Returns true if extent values look like WGS84 lon/lat (not projected coords).
 * Used to avoid using COG GeoTIFF extent (which may be in State Plane, UTM) as WGS84.
 */
export function looksLikeWgs84Extent(
  extent: number[] | null | undefined
): boolean {
  if (!extent || extent.length < 2) return false;
  const lon = extent[0];
  const lat = extent[1];
  return lon >= -180 && lon <= 180 && lat >= -90 && lat <= 90;
}

type GeoJsonGeometryForDisplay =
  | GeoJSON.Polygon
  | GeoJSON.MultiPolygon
  | GeoJSON.Point
  | GeoJSON.LineString
  | GeoJSON.MultiPoint
  | GeoJSON.MultiLineString;

/** Check if a coordinate pair is valid for Leaflet (finite numbers, WGS84 bounds). */
function isValidCoord(lon: unknown, lat: unknown): boolean {
  const l = typeof lon === 'number' && Number.isFinite(lon) ? lon : NaN;
  const a = typeof lat === 'number' && Number.isFinite(lat) ? lat : NaN;
  return !Number.isNaN(l) && !Number.isNaN(a) && a >= -90 && a <= 90 && l >= -180 && l <= 180;
}

/**
 * Recursively validate that GeoJSON coordinates are valid for Leaflet.
 * Rejects null, undefined, NaN, or out-of-range values.
 */
function hasValidGeoJsonCoordinates(coords: unknown): boolean {
  if (!Array.isArray(coords)) return false;
  const first = coords[0];
  if (first === null || first === undefined) return false;
  if (typeof first === 'number') {
    const lon = first;
    const lat = Array.isArray(coords) && coords.length >= 2 ? coords[1] : undefined;
    return isValidCoord(lon, lat);
  }
  if (Array.isArray(first)) {
    return (coords as unknown[]).every((c) => hasValidGeoJsonCoordinates(c));
  }
  return false;
}

/**
 * Returns true if the geometry is safe to pass to Leaflet (no undefined/NaN/out-of-range coords).
 */
export function isValidGeoJsonForLeaflet(
  geom: GeoJSON.Geometry | GeoJSON.Feature | GeoJSON.FeatureCollection | null | undefined
): boolean {
  if (!geom || typeof geom !== 'object') return false;
  const g = 'geometry' in geom ? (geom as GeoJSON.Feature).geometry : (geom as GeoJSON.Geometry);
  if (!g || typeof g !== 'object' || !('coordinates' in g)) return false;
  return hasValidGeoJsonCoordinates((g as { coordinates: unknown }).coordinates);
}

/**
 * Convert geometry (locn_geometry, etc.) to GeoJSON for map display.
 * Handles WKT (POLYGON, MULTIPOLYGON, ENVELOPE), GeoJSON object/string, and GeoJSON Feature.
 * Does NOT use dcat_bbox - use locn_geometry for the actual shape.
 */
export function geometryToGeoJSONForDisplay(
  geometry: string | object | null | undefined
): GeoJsonGeometryForDisplay | null {
  if (geometry == null) return null;

  // Already a GeoJSON object
  if (typeof geometry === 'object' && geometry !== null) {
    const g = geometry as { type?: string; coordinates?: unknown; geometry?: unknown };
    if (g.type === 'Feature' && g.geometry && typeof g.geometry === 'object') {
      return geometryToGeoJSONForDisplay(g.geometry);
    }
    if (g.type && g.coordinates) {
      return g as GeoJsonGeometryForDisplay;
    }
  }

  if (typeof geometry !== 'string') return null;
  const s = geometry.trim();

  // GeoJSON string
  if (s.startsWith('{')) {
    try {
      const parsed = JSON.parse(s) as { type?: string; coordinates?: unknown; geometry?: unknown };
      if (parsed?.type === 'Feature' && parsed?.geometry) {
        return geometryToGeoJSONForDisplay(parsed.geometry);
      }
      if (parsed?.type && parsed?.coordinates) {
        return parsed as GeoJsonGeometryForDisplay;
      }
    } catch {
      // not valid JSON
    }
    return null;
  }

  // WKT
  const fromWkt = wktToGeoJSON(s);
  return fromWkt;
}

/**
 * Result-like shape for hover geometry extraction (avoids circular import).
 */
interface ResultLike {
  attributes?: {
    ogm?: {
      locn_geometry?: string | object;
      locn_geometry_original?: string | object;
      dcat_bbox?: string;
    };
  };
  meta?: {
    ui?: {
      viewer?: {
        geometry?: string | object;
      };
    };
  };
}

/**
 * Get the hover geometry for a search result for map highlight.
 * Uses the SAME pipeline as resource page LocationMap: normalizeGeometry on the same
 * geometry sources (viewer.geometry, locn_geometry_original, locn_geometry).
 * Returns JSON string of normalized Polygon/MultiPolygon, or null.
 */
export function getHoverGeometryForResult(result: ResultLike): string | null {
  const ogm = result?.attributes?.ogm;
  const viewerGeom = result?.meta?.ui?.viewer?.geometry;
  const locnGeom =
    ogm?.locn_geometry_original ?? ogm?.locn_geometry ?? undefined;

  // Same priority and normalizer as resource page LocationMap
  const raw = viewerGeom ?? locnGeom ?? undefined;
  if (raw === undefined) return null;

  const normalized = normalizeGeometry(
    raw as string | GeoJSON.Polygon | GeoJSON.MultiPolygon | { wkt: string } | null
  );
  if (!normalized) return null;

  try {
    return JSON.stringify(normalized);
  } catch {
    return null;
  }
}

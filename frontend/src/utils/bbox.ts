/**
 * Parse dcat_bbox string (ENVELOPE or CSV) to Leaflet bounds [[south, west], [north, east]].
 * Returns null if the string cannot be parsed.
 */
const WEB_MERCATOR_TILE_SIZE = 256;
const WEB_MERCATOR_MAX_LAT = 85.05112878;

export interface BBoxSearchEnvelope {
  topLeft: {
    lat: number;
    lon: number;
  };
  bottomRight: {
    lat: number;
    lon: number;
  };
}

export function parseBboxToLeafletBounds(
  bboxStr: string | undefined
): [[number, number], [number, number]] | null {
  if (!bboxStr || typeof bboxStr !== 'string') return null;

  let coords: [number, number, number, number] | null = null; // [minX, minY, maxX, maxY] (lon, lat)

  const envelopeMatch = bboxStr.match(
    /ENVELOPE\s*\(\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\)/i
  );
  if (envelopeMatch) {
    const minX = parseFloat(envelopeMatch[1]);
    const maxX = parseFloat(envelopeMatch[2]);
    const maxY = parseFloat(envelopeMatch[3]);
    const minY = parseFloat(envelopeMatch[4]);
    coords = [minX, minY, maxX, maxY];
  } else {
    const parts = bboxStr.split(',').map((s) => parseFloat(s.trim()));
    if (parts.length === 4 && parts.every((n) => !isNaN(n))) {
      coords = [parts[0], parts[1], parts[2], parts[3]];
    }
  }

  if (!coords) return null;

  // Leaflet: [[south, west], [north, east]]
  return [
    [coords[1], coords[0]],
    [coords[3], coords[2]],
  ];
}

function clampLatitude(latitude: number): number {
  return Math.max(-WEB_MERCATOR_MAX_LAT, Math.min(WEB_MERCATOR_MAX_LAT, latitude));
}

function longitudeToWorldX(longitude: number, scale: number): number {
  return ((longitude + 180) / 360) * scale;
}

function latitudeToWorldY(latitude: number, scale: number): number {
  const clampedLatitude = clampLatitude(latitude);
  const sinLatitude = Math.sin((clampedLatitude * Math.PI) / 180);
  return (
    (0.5 - Math.log((1 + sinLatitude) / (1 - sinLatitude)) / (4 * Math.PI)) *
    scale
  );
}

function worldXToLongitude(worldX: number, scale: number): number {
  return (worldX / scale) * 360 - 180;
}

function worldYToLatitude(worldY: number, scale: number): number {
  const mercatorN = Math.PI - (2 * Math.PI * worldY) / scale;
  return (180 / Math.PI) * Math.atan(Math.sinh(mercatorN));
}

export function getStaticMapSearchEnvelope(
  latitude: number,
  longitude: number,
  zoom: number,
  width = 640,
  height = 320
): BBoxSearchEnvelope {
  const scale = WEB_MERCATOR_TILE_SIZE * 2 ** zoom;
  const centerX = longitudeToWorldX(longitude, scale);
  const centerY = latitudeToWorldY(latitude, scale);
  const topLeftX = centerX - width / 2;
  const topLeftY = centerY - height / 2;
  const bottomRightX = centerX + width / 2;
  const bottomRightY = centerY + height / 2;

  return {
    topLeft: {
      lat: worldYToLatitude(topLeftY, scale),
      lon: worldXToLongitude(topLeftX, scale),
    },
    bottomRight: {
      lat: worldYToLatitude(bottomRightY, scale),
      lon: worldXToLongitude(bottomRightX, scale),
    },
  };
}

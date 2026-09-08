import { cellToBoundary } from 'h3-js';

type Vertex = [number, number];

/** Clip an open polygon ring to one side of the antimeridian. */
function clipAtAntimeridian(vertices: Vertex[], keepWest: boolean): Vertex[] {
  const inside = ([lng]: Vertex) => (keepWest ? lng <= 180 : lng >= 180);
  const result: Vertex[] = [];
  let previous = vertices[vertices.length - 1];
  for (const current of vertices) {
    if (inside(previous) !== inside(current)) {
      const fraction = (180 - previous[0]) / (current[0] - previous[0]);
      result.push([180, previous[1] + fraction * (current[1] - previous[1])]);
    }
    if (inside(current)) result.push(current);
    previous = current;
  }
  return result;
}

/** Keep dateline-crossing cells local instead of drawing edges across the world. */
export function h3CellGeometry(
  h3: string
): GeoJSON.Polygon | GeoJSON.MultiPolygon {
  const ring: Vertex[] = cellToBoundary(h3).map(([lat, lng]) => [lng, lat]);
  const crossesDateline = ring.some(
    ([lng], i) => Math.abs(lng - ring[(i + 1) % ring.length][0]) > 180
  );
  if (!crossesDateline) {
    return { type: 'Polygon', coordinates: [[...ring, ring[0]]] };
  }

  // Work in a continuous longitude interval before clipping at +180. Shift
  // the eastern piece back to -180 so both pieces are valid GeoJSON rings.
  const unwrapped: Vertex[] = ring.map(([lng, lat]) => [
    lng < 0 ? lng + 360 : lng,
    lat,
  ]);
  const pieces = [true, false].map((keepWest) => {
    const clipped = clipAtAntimeridian(unwrapped, keepWest);
    const normalized: Vertex[] = clipped.map(([lng, lat]) => [
      keepWest ? lng : lng - 360,
      lat,
    ]);
    return [...normalized, normalized[0]];
  });
  return { type: 'MultiPolygon', coordinates: pieces.map((piece) => [piece]) };
}

export type HexBoundingBox = {
  west: number;
  south: number;
  east: number;
  north: number;
};

/** A west > east bbox represents the short interval crossing the dateline. */
export function getHexBoundingBox(h3: string): HexBoundingBox {
  const vertices = cellToBoundary(h3);
  const lats = vertices.map(([lat]) => lat);
  const lngs = vertices.map(([, lng]) => lng);
  const crossesDateline = Math.max(...lngs) - Math.min(...lngs) > 180;
  const continuous = lngs.map((lng) =>
    crossesDateline && lng < 0 ? lng + 360 : lng
  );
  const west = Math.min(...continuous);
  const east = Math.max(...continuous);
  return {
    west: west > 180 ? west - 360 : west,
    south: Math.min(...lats),
    east: east > 180 ? east - 360 : east,
    north: Math.max(...lats),
  };
}

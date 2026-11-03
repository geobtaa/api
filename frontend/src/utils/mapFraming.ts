import { LngLatBounds, type LngLatBoundsLike } from 'maplibre-gl';
import type { OgmRecord, Resource } from 'ogm-viewer/lib';

type Bounds = [number, number, number, number];

export function validBounds(
  value: LngLatBoundsLike | undefined
): Bounds | undefined {
  if (!value) return;
  try {
    // Bounds may come from OGM Viewer's separate MapLibre bundle.
    const portable = 'toArray' in value ? value.toArray() : value;
    const b = LngLatBounds.convert(portable);
    const [w, s, rawEast, n] = [
      b.getWest(),
      b.getSouth(),
      b.getEast(),
      b.getNorth(),
    ];
    const e = rawEast < w ? rawEast + 360 : rawEast;
    if (
      [w, s, e, n].every(Number.isFinite) &&
      s >= -90 &&
      n <= 90 &&
      s <= n &&
      e - w <= 360
    )
      return [w, s, e, n];
  } catch {
    /* Invalid metadata must not prevent a preview. */
  }
}

/** Union longitude intervals on a circle, preserving all coverage rather than choosing a cluster. */
export function unionFramingBounds(bounds: Bounds[]): Bounds | undefined {
  if (!bounds.length) return;
  const south = Math.min(...bounds.map((b) => b[1]));
  const north = Math.max(...bounds.map((b) => b[3]));
  const intervals: [number, number][] = [];
  for (const [w, , e] of bounds) {
    if (e - w >= 359.999) return [-180, south, 180, north];
    const start = ((w % 360) + 360) % 360;
    const end = start + e - w;
    if (end > 360) intervals.push([start, 360], [0, end - 360]);
    else intervals.push([start, end]);
  }
  intervals.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const interval of intervals) {
    const last = merged.at(-1);
    if (last && interval[0] <= last[1])
      last[1] = Math.max(last[1], interval[1]);
    else merged.push([...interval]);
  }
  let gap = -1,
    start = 0;
  merged.forEach((interval, i) => {
    const next =
      merged[(i + 1) % merged.length][0] + (i === merged.length - 1 ? 360 : 0);
    if (next - interval[1] > gap) {
      gap = next - interval[1];
      start = next % 360;
    }
  });
  const west = start >= 180 ? start - 360 : start;
  return [west, south, west + 360 - gap, north];
}

/** Keep connected geometry intact; wrap the spaces between separate features. */
export function geojsonFramingBounds(data: unknown): Bounds | undefined {
  const pieces: Bounds[] = [];
  let invalid = false;
  function visit(value: unknown) {
    if (!value || typeof value !== 'object') return;
    const g = value as Record<string, unknown>;
    if (g.type === 'FeatureCollection' && Array.isArray(g.features))
      g.features.forEach(visit);
    else if (g.type === 'Feature') visit(g.geometry);
    else if (g.type === 'GeometryCollection' && Array.isArray(g.geometries))
      g.geometries.forEach(visit);
    else if (g.type === 'MultiPoint' && Array.isArray(g.coordinates)) {
      g.coordinates.forEach((point) => {
        if (Array.isArray(point)) coordinates(point);
      });
    } else if (Array.isArray(g.coordinates)) coordinates(g.coordinates);
  }
  function coordinates(coords: unknown[]) {
    if (typeof coords[0] === 'number') {
      const [x, y] = coords as number[];
      if (
        !Number.isFinite(x) ||
        !Number.isFinite(y) ||
        Math.abs(x) > 180 ||
        Math.abs(y) > 90
      ) {
        invalid = true;
        return;
      }
      pieces.push([x, y, x, y]);
    } else if (Array.isArray(coords[0]) && typeof coords[0][0] === 'number') {
      const points = coords as number[][];
      if (
        points.some(
          (p) =>
            !Number.isFinite(p[0]) ||
            !Number.isFinite(p[1]) ||
            Math.abs(p[0]) > 180 ||
            Math.abs(p[1]) > 90
        )
      ) {
        invalid = true;
        return;
      }
      let prev = points[0][0],
        min = prev,
        max = prev;
      for (let i = 1; i < points.length; i++) {
        let delta = points[i][0] - points[i - 1][0];
        // An explicit full-world edge is not a zero-width dateline crossing.
        if (Math.abs(delta) < 360) {
          if (delta > 180) delta -= 360;
          if (delta < -180) delta += 360;
        }
        prev += delta;
        min = Math.min(min, prev);
        max = Math.max(max, prev);
      }
      pieces.push([
        min,
        Math.min(...points.map((p) => p[1])),
        max,
        Math.max(...points.map((p) => p[1])),
      ]);
    } else
      coords.forEach((c) => {
        if (Array.isArray(c)) coordinates(c);
      });
  }
  visit(data);
  return invalid ? undefined : unionFramingBounds(pieces);
}

/** Override only the preview camera accessor; retain original JSON and coverage geometry. */
export async function frameViewerRecord(
  record: OgmRecord,
  resources: Resource[]
): Promise<OgmRecord> {
  let declared: Bounds | undefined;
  try {
    declared = validBounds(record.getBounds());
  } catch {
    /* Fall back to source metadata. */
  }
  if (declared && declared[2] - declared[0] < 350) return record;
  const candidates = resources.filter(
    (r) => !['location', 'iiif-image', 'iiif-manifest'].includes(r.kind)
  );
  if (!candidates.length || candidates.length > 4) return record;
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const bounds = await Promise.race([
      Promise.all(
        candidates.map(async (resource) => {
          try {
            if (
              (resource.kind === 'geojson' ||
                resource.kind === 'openindexmap') &&
              'getData' in resource
            ) {
              return geojsonFramingBounds(
                await (
                  resource as Resource & { getData(): Promise<unknown> }
                ).getData()
              );
            }
            return validBounds(await resource.getReportedBounds());
          } catch {
            return undefined;
          }
        })
      ),
      new Promise<undefined>((resolve) => {
        timer = setTimeout(() => resolve(undefined), 5000);
      }),
    ]);
    // Do not crop a multi-source record when one source's coverage is unknown.
    if (!bounds || bounds.some((b) => !b)) return record;
    const chosen = unionFramingBounds(bounds as Bounds[]);
    if (!chosen) return record;
    const originalGeometry = record.getGeometry.bind(record);
    const framed = Object.create(record) as OgmRecord;
    // Let OGM Viewer construct its own bounds instance. Passing an instance
    // from the app's MapLibre bundle fails its runtime instanceof checks.
    const { OgmRecord: ViewerRecord } = await import('ogm-viewer/lib');
    const cameraRecord = new ViewerRecord({
      ...record.json,
      dcat_bbox: `ENVELOPE(${chosen[0]}, ${chosen[2]}, ${chosen[3]}, ${chosen[1]})`,
    });
    framed.getBounds = () => cameraRecord.getBounds();
    framed.getGeometry = originalGeometry;
    return framed;
  } finally {
    clearTimeout(timer);
  }
}

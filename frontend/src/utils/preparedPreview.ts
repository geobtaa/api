import type { OgmRecord } from 'ogm-viewer/lib';

export interface PreviewRecipe {
  kind: 'rgb' | 'scalar' | 'classified' | 'vector';
  bands: number[];
  value_range?: [number, number] | null;
  palette?: Record<string, [number, number, number, number]> | null;
  nodata?: number | null;
  color?: string;
  fill_opacity?: number;
  stroke_width?: number;
  point_radius?: number;
  thumbnail_bounds?: [number, number, number, number] | null;
}

export interface PreparedLayer {
  id: string;
  name: string;
  url: string;
  format: string;
  source_layer?: string | null;
  bounds?: [number, number, number, number];
  recipe?: PreviewRecipe;
}

export interface PreviewDescription {
  version: string;
  status: string;
  scope?: 'resource' | 'sample';
  layers: PreparedLayer[];
  transformations?: string[];
}

export interface PreviewHost {
  meta?: { ui?: { preview?: PreviewDescription } };
}

type PreparedMapLayer = PreparedLayer & { format: 'cog' | 'pmtiles' };

function cameraBounds(layer: PreparedLayer) {
  const bounds = layer.recipe?.thumbnail_bounds ?? layer.bounds;
  if (!bounds) return bounds;
  const [west, south, east, north] = bounds;
  // A point/straight line has a valid geographic extent but cannot define a
  // useful fitted camera. Pad only the runtime camera, never API coverage.
  return [
    west === east ? Math.max(-180, west - 0.01) : west,
    south === north ? Math.max(-90, south - 0.01) : south,
    west === east ? Math.min(180, east + 0.01) : east,
    south === north ? Math.min(90, north + 0.01) : north,
  ] as [number, number, number, number];
}

export function readyPreparedLayers(data: PreviewHost): PreparedMapLayer[] {
  const preview = data.meta?.ui?.preview;
  if (preview?.status !== 'ready' || preview.version !== '1') return [];
  return preview.layers.filter(
    (layer): layer is PreparedMapLayer =>
      ['cog', 'pmtiles'].includes(layer.format) && Boolean(layer.url)
  );
}

/** Attach runtime sources; source record JSON and original downloads stay intact. */
export function attachPreparedPreview(record: OgmRecord, data: PreviewHost) {
  const layers = readyPreparedLayers(data).map((layer) => ({
    ...layer,
    bounds: cameraBounds(layer),
  }));
  (
    record as OgmRecord & { preparedPreviews?: PreparedMapLayer[] }
  ).preparedPreviews = layers;
  return record;
}

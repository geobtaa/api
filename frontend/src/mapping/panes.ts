import type { AddLayerObject, Map } from 'maplibre-gl';

/** Transparent anchors preserve pane order even when asynchronous overlays arrive later. */
export function ensurePane(map: Map, order: number): string {
  const id = `app-pane-${order}`;
  if (!map.getLayer(id)) {
    const before = map
      .getStyle()
      .layers.find(
        (layer) =>
          layer.id.startsWith('app-pane-') && Number(layer.id.slice(9)) > order
      )?.id;
    map.addLayer(
      { id, type: 'background', paint: { 'background-opacity': 0 } },
      before
    );
  }
  return id;
}

export function addPaneLayer(map: Map, layer: AddLayerObject, order = 400) {
  ensurePane(map, 400);
  ensurePane(map, order);
  const before = map
    .getStyle()
    .layers.find(
      (existing) =>
        existing.id.startsWith('app-pane-') &&
        Number(existing.id.slice(9)) > order
    )?.id;
  map.addLayer(layer, before);
}

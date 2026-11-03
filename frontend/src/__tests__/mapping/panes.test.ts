import type { AddLayerObject, Map as NativeMap } from 'maplibre-gl';
import { expect, it, vi } from 'vitest';
import { addPaneLayer, ensurePane } from '../../mapping/panes';
import { addFeaturedPins } from '../../components/home/featuredPins';

function nativeMap() {
  const layers: AddLayerObject[] = [];
  const map = {
    getStyle: () => ({ layers }),
    getLayer: (id: string) => layers.find((layer) => layer.id === id),
    addLayer: (layer: AddLayerObject, before?: string) => {
      const index = layers.findIndex((existing) => existing.id === before);
      layers.splice(index < 0 ? layers.length : index, 0, layer);
    },
    removeLayer: (id: string) =>
      layers.splice(
        layers.findIndex((layer) => layer.id === id),
        1
      ),
    // Skip canvas drawing here; Chrome verification exercises actual image creation.
    hasImage: () => true,
    setLayoutProperty: vi.fn(),
  };
  return {
    map: map as unknown as NativeMap,
    layers,
    visibility: map.setLayoutProperty,
  };
}
it('keeps late H3 refreshes and toggles below bounds and the Allmaps preview', () => {
  const { map, layers } = nativeMap();
  addPaneLayer(map, { id: 'allmaps', type: 'background' }, 420);
  addPaneLayer(map, { id: 'bounds', type: 'background' }, 410);
  addPaneLayer(map, { id: 'hexes', type: 'background' });
  const ids = () =>
    layers.map((layer) => layer.id).filter((id) => !id.startsWith('app-pane-'));
  expect(ids()).toEqual(['hexes', 'bounds', 'allmaps']);
  map.removeLayer('hexes');
  addPaneLayer(map, { id: 'new-hexes', type: 'background' });
  expect(ids()).toEqual(['new-hexes', 'bounds', 'allmaps']);
});
it('keeps late overlays below OGM layers attached to the top of the style', () => {
  const { map, layers } = nativeMap();
  ensurePane(map, 400);
  ensurePane(map, 420);
  map.addLayer({ id: 'ogm-route', type: 'line', source: 'routes' });
  addPaneLayer(map, { id: 'hexes', type: 'background' });
  expect(layers.findIndex((layer) => layer.id === 'hexes')).toBeLessThan(
    layers.findIndex((layer) => layer.id === 'ogm-route')
  );
});
it('shows overlapping coastal features as pins and cleans them up on slide changes', () => {
  const { map, layers, visibility } = nativeMap();
  map.addLayer({
    id: 'coast-points',
    type: 'circle',
    source: 'coast',
    'source-layer': 'beaches',
    filter: ['==', ['geometry-type'], 'Point'],
    minzoom: 3,
    maxzoom: 15,
  });
  const clear = addFeaturedPins(map, ['coast-points']);
  const pin = layers.find((layer) => layer.id === 'coast-points-featured-pins');
  expect(pin).toMatchObject({
    type: 'symbol',
    source: 'coast',
    'source-layer': 'beaches',
    minzoom: 3,
    maxzoom: 15,
    layout: {
      'icon-anchor': 'bottom',
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
    },
  });
  expect(visibility).toHaveBeenCalledWith('coast-points', 'visibility', 'none');
  clear();
  expect(map.getLayer('coast-points-featured-pins')).toBeUndefined();
  expect(visibility).toHaveBeenLastCalledWith(
    'coast-points',
    'visibility',
    'visible'
  );
});

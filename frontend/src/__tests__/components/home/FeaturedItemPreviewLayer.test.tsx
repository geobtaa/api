import { act, render, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { FeaturedItemPreviewLayer } from '../../../components/home/FeaturedItemPreviewLayer';
import type { GeoDocumentDetails } from '../../../types/api';

const state = vi.hoisted(() => ({
  instances: [] as Array<{ id: string; reject?: (error: Error) => void }>,
  layers: new Map<string, { implementation: unknown }>(),
  remove: vi.fn(),
}));
vi.mock('../../../mapping/react', () => ({
  useMap: () => map,
}));
const map = {
  whenReady: (callback: () => void) => callback(),
  native: {
    getLayer: (id: string) => state.layers.get(id),
    removeLayer: (id: string) => {
      state.remove(id);
      state.layers.delete(id);
    },
  },
};
vi.mock('../../../mapping/panes', () => ({
  addPaneLayer: (_map: unknown, layer: { id: string }) =>
    state.layers.set(layer.id, { implementation: layer }),
}));
vi.mock('@allmaps/maplibre', () => ({
  WarpedMapLayer: class {
    id: string;
    reject?: (error: Error) => void;
    constructor(options: { layerId: string }) {
      this.id = options.layerId;
      state.instances.push(this);
    }
    addGeoreferenceAnnotation() {
      return new Promise((_resolve, reject) => {
        this.reject = reject;
      });
    }
  },
}));
const detail = (url: string) =>
  ({
    meta: {
      ui: { allmaps: { allmaps_annotated: true, allmaps_annotation_url: url } },
    },
  }) as GeoDocumentDetails;
beforeEach(() => {
  vi.clearAllMocks();
  state.instances = [];
  state.layers.clear();
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
  );
});
it('preserves the active preview when other thumbnail details arrive and ignores stale cleanup', async () => {
  const first = detail('https://example.org/first');
  const second = detail('https://example.org/second');
  const view = render(
    <FeaturedItemPreviewLayer
      activeIndex={0}
      featuredDetails={[first, null]}
      featuredInitiated
    />
  );
  await waitFor(() => expect(state.instances).toHaveLength(1));
  view.rerender(
    <FeaturedItemPreviewLayer
      activeIndex={0}
      featuredDetails={[first, second]}
      featuredInitiated
    />
  );
  expect(state.instances).toHaveLength(1);
  expect(state.remove).not.toHaveBeenCalled();
  view.rerender(
    <FeaturedItemPreviewLayer
      activeIndex={1}
      featuredDetails={[first, second]}
      featuredInitiated
    />
  );
  await waitFor(() => expect(state.instances).toHaveLength(2));
  expect(state.remove).toHaveBeenCalledTimes(1);
  await act(async () =>
    state.instances[0].reject!(new Error('Old annotation failed'))
  );
  expect(state.layers.get('featured-allmaps')?.implementation).toBe(
    state.instances[1]
  );
  expect(state.remove).toHaveBeenCalledTimes(1);
  view.unmount();
  expect(state.layers.size).toBe(0);
});

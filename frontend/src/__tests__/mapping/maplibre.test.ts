/* eslint-disable @typescript-eslint/no-explicit-any -- Native map test double. */
import { beforeEach, describe, expect, it, vi } from 'vitest';
const mocks = vi.hoisted(() => ({ instances: [] as any[], webgl: true }));
vi.mock('maplibre-gl', () => ({
  setWorkerUrl: vi.fn(),
  NavigationControl: class {},
  FullscreenControl: class {},
  Popup: class {},
  Map: class {
    sources = new Map();
    layers = new Map();
    handlers = new Map();
    loaded = true;
    addSource = vi.fn((id, data) => this.sources.set(id, data));
    addLayer = vi.fn((l) => this.layers.set(l.id, l));
    removeLayer = vi.fn((id) => this.layers.delete(id));
    removeSource = vi.fn((id) => this.sources.delete(id));
    getLayer = (id) => this.layers.get(id);
    getSource = (id) => this.sources.get(id);
    addControl = vi.fn();
    remove = vi.fn();
    resize = vi.fn();
    jumpTo = vi.fn();
    fitBounds = vi.fn();
    setFeatureState = vi.fn();
    getCanvas = () => ({
      style: {},
      getContext: () => (mocks.webgl ? {} : null),
    });
    isStyleLoaded = () => this.loaded;
    constructor(public options) {
      mocks.instances.push(this);
    }
    on = vi.fn();
    off = vi.fn();
    once = (n, f) => this.handlers.set(n, f);
  },
}));
import { Map as AppMap, geoJSON, latLngBounds } from '../../mapping/maplibre';
beforeEach(() => {
  mocks.instances = [];
  mocks.webgl = true;
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      disconnect() {}
    }
  );
});
describe('MapLibre mapping boundary', () => {
  it('cleans up the native map when WebGL is unavailable', () => {
    mocks.webgl = false;
    expect(() => new AppMap(document.createElement('div'))).toThrow(
      'WebGL2 is unavailable'
    );
    expect(mocks.instances[0].remove).toHaveBeenCalledTimes(1);
  });
  it('converts legacy camera units and enables cooperative gestures', () => {
    const map = new AppMap(document.createElement('div'), {
      center: [40, -90],
      zoom: 5,
    });
    const native = mocks.instances[0];
    expect(native.options.center).toEqual([-90, 40]);
    expect(native.options.zoom).toBe(4);
    expect(native.options.cooperativeGestures).toBe(true);
    map.setView([10, 20], 3);
    expect(native.jumpTo).toHaveBeenCalledWith({ center: [20, 10], zoom: 2 });
    map.remove();
  });
  it('batches features into one source while preserving polygon holes', () => {
    const map = new AppMap(document.createElement('div'));
    const geometry = {
      type: 'Polygon',
      coordinates: [
        [
          [0, 0],
          [5, 0],
          [5, 5],
          [0, 0],
        ],
        [
          [1, 1],
          [2, 1],
          [2, 2],
          [1, 1],
        ],
      ],
    };
    const layer = geoJSON({
      type: 'FeatureCollection',
      features: [
        { type: 'Feature', properties: {}, geometry },
        { type: 'Feature', properties: {}, geometry },
      ],
    }).addTo(map);
    const native = mocks.instances[0];
    expect(native.addSource).toHaveBeenCalledTimes(1);
    expect(native.addSource.mock.calls[0][1].data.features[0].geometry).toEqual(
      geometry
    );
    expect(native.addLayer).toHaveBeenCalledTimes(4);
    layer.remove();
    expect(native.sources.size).toBe(0);
    expect(native.layers.size).toBe(0);
    map.remove();
  });
  it('does not install a removed layer when the style finishes loading', () => {
    const map = new AppMap(document.createElement('div'));
    const native = mocks.instances[0];
    native.loaded = false;
    const layer = geoJSON({ type: 'Point', coordinates: [1, 2] }).addTo(map);
    layer.remove();
    native.handlers.get('load')();
    expect(native.addSource).not.toHaveBeenCalled();
    map.remove();
  });
  it('updates hover styling without rebuilding source data', () => {
    const map = new AppMap(document.createElement('div'));
    const layer = geoJSON({ type: 'Point', coordinates: [1, 2] }).addTo(map);
    layer.eachLayer((child) => child.setStyle({ color: '#fff' }));
    const native = mocks.instances[0];
    expect(native.addSource).toHaveBeenCalledTimes(1);
    expect(native.setFeatureState).toHaveBeenCalled();
    map.remove();
  });
  it('keeps longitude and latitude ordered in bounds and clamps polar camera latitude', () => {
    const bounds = latLngBounds([
      [-90, -180],
      [90, 180],
    ]);
    expect(bounds.toBBoxString()).toBe('-180,-90,180,90');
    expect(bounds.toArray()).toEqual([
      [-180, -85.05112878],
      [180, 85.05112878],
    ]);
    expect(bounds.contains([0, 0])).toBe(true);
  });
});

import { beforeEach, describe, expect, it, vi } from 'vitest';
import L from 'leaflet';

const mocks = vi.hoisted(() => ({
  getCookie: vi.fn(),
}));

vi.mock('js-cookie', () => ({
  default: {
    get: mocks.getCookie,
    set: vi.fn(),
  },
}));

import {
  attachBasemapSwitcher,
  attachViewerBasemapSwitcher,
  createBasemapLayer,
  getAvailableBasemapKeys,
  getSavedBasemapKey,
} from '../config/basemaps';
import geoblacklightBasemaps from '../geoblacklight/basemaps';
import geoblacklightOpenlayersBasemaps from '../geoblacklight/openlayers_basemaps';

describe('basemap preferences', () => {
  beforeEach(() => {
    mocks.getCookie.mockReset();
  });

  it('defaults to OpenStreetMap when no preference is saved', () => {
    mocks.getCookie.mockReturnValue(undefined);

    expect(getSavedBasemapKey()).toBe('openStreetMap');
  });

  it('continues to honor a valid saved preference', () => {
    mocks.getCookie.mockReturnValue('esriWorldImagery');

    expect(getSavedBasemapKey()).toBe('esriWorldImagery');
  });

  it('offers only the configured OpenStreetMap and imagery basemaps', () => {
    expect(getAvailableBasemapKeys()).toEqual([
      'openStreetMap',
      'esriWorldImagery',
    ]);
  });

  it('limits the GeoBlacklight viewer catalog to OpenStreetMap', () => {
    expect(Object.keys(geoblacklightBasemaps)).toEqual([
      'openstreetmapStandard',
    ]);
    expect(Object.values(geoblacklightOpenlayersBasemaps)).toEqual([
      expect.objectContaining({
        url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      }),
    ]);
  });

  it('falls back to OpenStreetMap when a saved preference is no longer supported', () => {
    mocks.getCookie.mockReturnValue('removedBasemap');

    expect(getSavedBasemapKey()).toBe('openStreetMap');
  });

  it('uses the canonical OpenStreetMap tile endpoint and attribution', () => {
    const tileLayer = vi.fn(() => ({}));
    const Leaflet = { tileLayer } as unknown as typeof L;

    createBasemapLayer(Leaflet, 'openStreetMap');

    expect(tileLayer).toHaveBeenCalledWith(
      'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
        zIndex: 0,
        referrerPolicy: 'strict-origin-when-cross-origin',
      }
    );
  });
});

describe('basemap tile failures', () => {
  it('keeps resource tiles above either basemap after switching', () => {
    mocks.getCookie.mockReturnValue(undefined);
    const element = document.createElement('div');
    document.body.appendChild(element);
    const map = L.map(element).setView([45, -93], 5);
    const cleanup = attachBasemapSwitcher(map, L);
    const overlay = L.tileLayer('/resource/{z}/{x}/{y}.png').addTo(map);
    try {
      const choices = element.querySelectorAll<HTMLInputElement>(
        '.leaflet-control-layers-selector'
      );
      for (const choice of [choices[1], choices[0], choices[1]]) {
        choice.click();
        map.eachLayer((layer) => {
          if (layer instanceof L.TileLayer && layer !== overlay) {
            expect(Number(layer.getContainer()!.style.zIndex)).toBeLessThan(
              Number(overlay.getContainer()!.style.zIndex)
            );
          }
        });
        expect(map.hasLayer(overlay)).toBe(true);
      }
    } finally {
      cleanup();
      map.remove();
      element.remove();
    }
  });

  it('preserves overlays, reports failures per layer, and detaches listeners on cleanup', () => {
    mocks.getCookie.mockReturnValue(undefined);
    const element = document.createElement('div');
    document.body.appendChild(element);
    const map = L.map(element).setView([45, -93], 5);
    const overlay = L.layerGroup().addTo(map);
    const onError = vi.fn();
    const cleanup = attachBasemapSwitcher(map, L, 'topleft', onError);
    let osm!: L.TileLayer;
    map.eachLayer((layer) => {
      if (layer instanceof L.TileLayer) osm = layer;
    });
    const tile = document.createElement('img');
    try {
      expect(onError).toHaveBeenLastCalledWith(false);
      osm.fire('tileerror', { tile });
      expect(tile.style.visibility).toBe('hidden');
      expect(onError).toHaveBeenLastCalledWith(true);
      expect(map.hasLayer(overlay)).toBe(true);
      osm.fire('tileload', { tile: document.createElement('img') });
      expect(onError).toHaveBeenLastCalledWith(true);

      const choices = element.querySelectorAll<HTMLInputElement>(
        '.leaflet-control-layers-selector'
      );
      choices[1].click();
      expect(onError).toHaveBeenLastCalledWith(false);
      // A late failure from the inactive layer must not affect the alternative.
      osm.fire('tileerror', { tile });
      expect(onError).toHaveBeenLastCalledWith(false);
      choices[0].click();
      expect(onError).toHaveBeenLastCalledWith(true);
      cleanup();
      onError.mockClear();
      osm.fire('tileerror', { tile });
      expect(onError).not.toHaveBeenCalled();
      expect(map.hasLayer(overlay)).toBe(true);
    } finally {
      map.remove();
      element.remove();
    }
  });
});

describe('large viewer basemap warning', () => {
  it('keeps its accessible warning inside the fullscreen map and cleans up on disconnect', () => {
    mocks.getCookie.mockReturnValue(undefined);
    const element = document.createElement('div');
    document.body.appendChild(element);
    const map = L.map(element).setView([45, -93], 5);
    const overlay = L.layerGroup().addTo(map);
    const cleanup = attachViewerBasemapSwitcher(map, L);
    let osm!: L.TileLayer;
    map.eachLayer((layer) => {
      if (layer instanceof L.TileLayer) osm = layer;
    });
    const message = element.querySelector<HTMLElement>('[role="status"]')!;
    try {
      expect(message.hidden).toBe(true);
      const tile = document.createElement('img');
      osm.fire('tileerror', { tile });
      expect(message.hidden).toBe(false);
      expect(message.textContent).toContain('Layers control');
      expect(tile.style.visibility).toBe('hidden');
      expect(map.hasLayer(overlay)).toBe(true);
      element
        .querySelectorAll<HTMLInputElement>(
          '.leaflet-control-layers-selector'
        )[1]
        .click();
      expect(message.hidden).toBe(true);
      cleanup();
      expect(element.querySelector('[role="status"]')).toBeNull();
      expect(osm.listens('tileerror')).toBe(false);
      expect(map.hasLayer(overlay)).toBe(true);
    } finally {
      map.remove();
      element.remove();
    }
  });
});

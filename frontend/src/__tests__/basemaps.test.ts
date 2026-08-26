import { beforeEach, describe, expect, it, vi } from 'vitest';
import type L from 'leaflet';

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
  createBasemapLayer,
  getAvailableBasemapKeys,
  getSavedBasemapKey,
} from '../config/basemaps';

describe('basemap preferences', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
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

  it('hides Carto and falls back to OpenStreetMap when no key is configured', () => {
    mocks.getCookie.mockReturnValue('cartoLight');

    expect(getAvailableBasemapKeys()).not.toContain('cartoLight');
    expect(getSavedBasemapKey()).toBe('openStreetMap');
  });

  it('uses the configured key for the optional Carto basemap', () => {
    vi.stubEnv('VITE_CARTO_BASEMAP_KEY', 'test key+/');
    mocks.getCookie.mockReturnValue('cartoLight');
    const tileLayer = vi.fn(() => ({}));
    const Leaflet = { tileLayer } as unknown as typeof L;

    expect(getAvailableBasemapKeys()).toContain('cartoLight');
    expect(getSavedBasemapKey()).toBe('cartoLight');

    createBasemapLayer(Leaflet, 'cartoLight');

    expect(tileLayer).toHaveBeenCalledWith(
      'https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png?key=test%20key%2B%2F',
      {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20,
      }
    );
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
      }
    );
  });
});

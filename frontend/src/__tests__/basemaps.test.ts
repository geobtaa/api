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

import { createBasemapLayer, getSavedBasemapKey } from '../config/basemaps';

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

  it('falls back to OpenStreetMap for the removed Carto preference', () => {
    mocks.getCookie.mockReturnValue('cartoLight');

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
      }
    );
  });
});

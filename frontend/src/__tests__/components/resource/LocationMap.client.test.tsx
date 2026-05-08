import { render, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import L from 'leaflet';
import LocationMap from '../../../components/resource/LocationMap.client';

const mockMapInstance = {
  setView: vi.fn().mockReturnThis(),
  eachLayer: vi.fn(),
  removeLayer: vi.fn(),
  fitBounds: vi.fn(),
  remove: vi.fn(),
  hasLayer: vi.fn().mockReturnValue(false),
};

vi.mock('leaflet/dist/leaflet.css', () => ({}));
vi.mock('../../../config/basemaps', () => ({
  attachBasemapSwitcher: vi.fn(() => vi.fn()),
}));

vi.mock('leaflet', () => ({
  default: {
    Handler: {
      extend: vi.fn((definition) => definition),
    },
    Map: {
      addInitHook: vi.fn(),
    },
    DomEvent: {
      on: vi.fn(),
      off: vi.fn(),
      preventDefault: vi.fn(),
    },
    DomUtil: {
      addClass: vi.fn(),
      removeClass: vi.fn(),
    },
    map: vi.fn(() => mockMapInstance),
    GeoJSON: class MockGeoJSON {},
    geoJSON: vi.fn(() => ({
      addTo: vi.fn().mockReturnThis(),
      getBounds: vi.fn(() => 'geometry-bounds'),
    })),
    latLng: vi.fn((lat, lng) => ({ lat, lng })),
    latLngBounds: vi.fn(() => 'multipolygon-bounds'),
    rectangle: vi.fn(() => ({
      addTo: vi.fn().mockReturnThis(),
    })),
  },
}));

describe('LocationMap client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('enables command/control gesture handling for scroll zoom', async () => {
    render(
      <LocationMap
        geometry={{
          type: 'Polygon',
          coordinates: [
            [
              [-93.3, 44.9],
              [-93.2, 44.9],
              [-93.2, 45],
              [-93.3, 45],
              [-93.3, 44.9],
            ],
          ],
        }}
      />
    );

    await waitFor(() => {
      expect(L.map).toHaveBeenCalledWith(
        expect.any(HTMLDivElement),
        expect.objectContaining({
          gestureHandling: true,
          scrollWheelZoom: true,
        })
      );
    });
  });
});

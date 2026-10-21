import { act, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import L from 'leaflet';
import { attachBasemapSwitcher } from '../../../config/basemaps';
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

describe('Location map basemap lifecycle', () => {
  beforeEach(() => vi.clearAllMocks());

  it.each([
    { type: 'Point' as const, coordinates: [-93, 45] },
    {
      type: 'Polygon' as const,
      coordinates: [
        [
          [-94, 44],
          [-92, 44],
          [-92, 46],
          [-94, 44],
        ],
      ],
    },
    {
      type: 'MultiPolygon' as const,
      coordinates: [
        [
          [
            [-94, 44],
            [-92, 44],
            [-92, 46],
            [-94, 44],
          ],
        ],
      ],
    },
  ])('sets the $type resource view before adding tiles', (geometry) => {
    const { unmount } = render(<LocationMap geometry={geometry} />);
    const view =
      geometry.type === 'Point'
        ? mockMapInstance.setView
        : mockMapInstance.fitBounds;
    expect(view.mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(attachBasemapSwitcher).mock.invocationCallOrder[0]
    );
    expect(mockMapInstance.setView).not.toHaveBeenCalledWith([0, 0], 2);
    unmount();
  });

  it('announces failures and clears the warning on switching or resource navigation', () => {
    const { rerender, unmount } = render(
      <LocationMap geometry={{ type: 'Point', coordinates: [-93, 45] }} />
    );
    const onError = vi.mocked(attachBasemapSwitcher).mock.calls[0][3]!;
    const cleanup = vi.mocked(attachBasemapSwitcher).mock.results[0].value;
    act(() => onError(true));
    expect(screen.getByRole('status')).toHaveTextContent(
      'Choose another basemap'
    );
    act(() => onError(false));
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    act(() => onError(true));
    rerender(
      <LocationMap geometry={{ type: 'Point', coordinates: [-94, 46] }} />
    );
    expect(cleanup).toHaveBeenCalledOnce();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    unmount();
  });
});

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { GeospatialFilterMap } from '../../components/search/GeospatialFilterMap.client';

const mockControl = { addTo: vi.fn(), remove: vi.fn() };
const mockMapInstance = {
  setView: vi.fn(),
  fitBounds: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
  remove: vi.fn(),
  invalidateSize: vi.fn(),
  addLayer: vi.fn(),
  removeLayer: vi.fn(),
  hasLayer: vi.fn().mockReturnValue(false),
  getZoom: vi.fn().mockReturnValue(6),
  getBounds: vi.fn().mockReturnValue({
    getNorthEast: () => ({ lat: 45, lng: -104 }),
    getSouthWest: () => ({ lat: 41, lng: -109 }),
    getWest: () => -109,
    getSouth: () => 41,
    getEast: () => -104,
    getNorth: () => 45,
  }),
};

vi.mock('leaflet', () => {
  return {
    default: {
      map: vi.fn(() => mockMapInstance),
      tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
      rectangle: vi.fn(() => ({ addTo: vi.fn() })),
      geoJSON: vi.fn(() => ({ addTo: vi.fn() })),
      latLngBounds: vi.fn(() => ({ isValid: () => true })),
      control: {
        layers: vi.fn(() => mockControl),
      },
    },
  };
});

vi.mock('h3-js', () => ({
  cellToBoundary: vi.fn(() => [
    [44, -108],
    [44, -107],
    [43, -107],
    [43, -108],
  ]),
}));

vi.mock('../../services/api', () => ({
  fetchMapH3: vi.fn().mockResolvedValue({ hexes: [] }),
}));

vi.mock('../../components/map/HexTableControl', () => ({
  HexTableControl: () => <div data-testid="hex-table-control" />,
}));

vi.mock('../../components/map/HexLayerToggleControl', () => ({
  HexLayerToggleControl: () => null,
}));

function SearchLocationProbe() {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
}

describe('GeospatialFilterMap client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    class MockIntersectionObserver {
      observe() {}
      disconnect() {}
    }
    Object.defineProperty(window, 'IntersectionObserver', {
      writable: true,
      configurable: true,
      value: MockIntersectionObserver,
    });
  });

  it('updates geo relation to precision when toggle is clicked', async () => {
    render(
      <MemoryRouter
        initialEntries={[
          '/search?include_filters[geo][type]=bbox&include_filters[geo][field]=dcat_bbox&include_filters[geo][top_left][lat]=45&include_filters[geo][top_left][lon]=-109&include_filters[geo][bottom_right][lat]=41&include_filters[geo][bottom_right][lon]=-104&include_filters[geo][relation]=intersects',
        ]}
      >
        <Routes>
          <Route
            path="/search"
            element={
              <>
                <GeospatialFilterMap />
                <SearchLocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    const precisionButton = await screen.findByRole('button', {
      name: 'Set map mode to precision',
    });
    fireEvent.click(precisionButton);

    await waitFor(() => {
      const search = screen.getByTestId('location-search').textContent ?? '';
      const params = new URLSearchParams(search);
      expect(params.get('include_filters[geo][relation]')).toBe('within');
    });
  });
});

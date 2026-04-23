import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { GeospatialFilterMap } from '../../components/search/GeospatialFilterMap.client';
import { fetchMapH3 } from '../../services/api';

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
  HexLayerToggleControl: ({
    enabled,
    onToggle,
  }: {
    enabled: boolean;
    onToggle: (enabled: boolean) => void;
  }) => (
    <div>
      <div data-testid="hex-enabled-state">{String(enabled)}</div>
      <button
        type="button"
        data-testid="hex-toggle-btn"
        onClick={() => onToggle(!enabled)}
      >
        Toggle hex
      </button>
    </div>
  ),
}));

vi.mock('../../components/map/MapGeosearchControl', () => ({
  MapGeosearchControl: () => <div data-testid="map-geosearch-control" />,
}));

function SearchLocationProbe() {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
}

describe('GeospatialFilterMap client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    localStorage.clear();
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

  it('waits until window load before issuing the initial hex request', async () => {
    vi.useFakeTimers();

    const originalReadyState = document.readyState;
    Object.defineProperty(document, 'readyState', {
      configurable: true,
      value: 'loading',
    });

    render(
      <MemoryRouter initialEntries={['/search?q=chicago&view=gallery']}>
        <Routes>
          <Route path="/search" element={<GeospatialFilterMap />} />
        </Routes>
      </MemoryRouter>
    );

    act(() => {
      vi.advanceTimersByTime(2000);
    });

    expect(fetchMapH3).not.toHaveBeenCalled();

    fireEvent(window, new Event('load'));

    act(() => {
      vi.advanceTimersByTime(249);
    });

    expect(fetchMapH3).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(1);
      await Promise.resolve();
    });

    expect(fetchMapH3).toHaveBeenCalledTimes(1);

    Object.defineProperty(document, 'readyState', {
      configurable: true,
      value: originalReadyState,
    });
  });

  it('fits to result hexes on the initial search load when no bbox is active', async () => {
    vi.useFakeTimers();
    vi.mocked(fetchMapH3).mockResolvedValueOnce({
      hexes: [{ h3: '8928308280fffff', count: 12 }],
    });
    const originalReadyState = document.readyState;
    Object.defineProperty(document, 'readyState', {
      configurable: true,
      value: 'complete',
    });

    render(
      <MemoryRouter initialEntries={['/search?q=st%20paul&view=gallery']}>
        <Routes>
          <Route path="/search" element={<GeospatialFilterMap />} />
        </Routes>
      </MemoryRouter>
    );

    await act(async () => {
      vi.advanceTimersByTime(250);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(fetchMapH3).toHaveBeenCalledTimes(1);
    expect(mockMapInstance.fitBounds).toHaveBeenCalledWith(
      expect.anything(),
      {
        padding: [24, 24],
        maxZoom: 14,
      }
    );

    Object.defineProperty(document, 'readyState', {
      configurable: true,
      value: originalReadyState,
    });
  });

  it('updates geo relation to within when toggle is clicked', async () => {
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

    const withinButton = await screen.findByRole('button', {
      name: 'Set map mode to within',
    });
    fireEvent.click(withinButton);

    await waitFor(() => {
      const search = screen.getByTestId('location-search').textContent ?? '';
      const params = new URLSearchParams(search);
      expect(params.get('include_filters[geo][relation]')).toBe('within');
    });
  });

  it('defaults bbox relation mode to overlap when relation is absent', async () => {
    render(
      <MemoryRouter
        initialEntries={[
          '/search?include_filters[geo][type]=bbox&include_filters[geo][field]=dcat_bbox&include_filters[geo][top_left][lat]=45&include_filters[geo][top_left][lon]=-109&include_filters[geo][bottom_right][lat]=41&include_filters[geo][bottom_right][lon]=-104',
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

    const withinButton = await screen.findByRole('button', {
      name: 'Set map mode to within',
    });
    const overlapButton = screen.getByRole('button', {
      name: 'Set map mode to overlap',
    });

    expect(withinButton).not.toHaveClass('bg-blue-600');
    expect(overlapButton).toHaveClass('bg-blue-600');
  });

  it('restores and persists hex layer preference via localStorage', async () => {
    localStorage.setItem('hex_layer_enabled', '0');

    render(
      <MemoryRouter initialEntries={['/search?q=']}>
        <Routes>
          <Route path="/search" element={<GeospatialFilterMap />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByTestId('hex-enabled-state')).toHaveTextContent(
      'false'
    );

    fireEvent.click(screen.getByTestId('hex-toggle-btn'));

    await waitFor(() => {
      expect(localStorage.getItem('hex_layer_enabled')).toBe('1');
    });
    expect(screen.getByTestId('hex-enabled-state')).toHaveTextContent('true');
  });
});

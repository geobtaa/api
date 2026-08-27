import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import L from 'leaflet';
import {
  MapProvider,
  useMap as useMapContext,
} from '../../../context/MapContext';
import { MapResultView } from '../../../components/search/MapResultView.client';
import type { GeoDocument } from '../../../types/api';

interface MockOmsInstance {
  markers: L.Marker[];
  addMarker: ReturnType<typeof vi.fn>;
  addListener: ReturnType<typeof vi.fn>;
  removeListener: ReturnType<typeof vi.fn>;
  clearMarkers: ReturnType<typeof vi.fn>;
  unspiderfy: ReturnType<typeof vi.fn>;
}

const { mockOmsInstances } = vi.hoisted(() => ({
  mockOmsInstances: [] as MockOmsInstance[],
}));

const mockFlyToBounds = vi.fn();
const mockMap = {
  flyToBounds: mockFlyToBounds,
  openPopup: vi.fn(),
  addLayer: vi.fn(),
  removeLayer: vi.fn(),
  hasLayer: vi.fn().mockReturnValue(false),
  eachLayer: vi.fn(),
  on: vi.fn(),
  off: vi.fn(),
  latLngToLayerPoint: vi.fn((latLng: L.LatLng) =>
    L.point(latLng.lng * 100, latLng.lat * 100)
  ),
};

vi.mock('leaflet/dist/leaflet.css', () => ({}));
vi.mock('react-leaflet', () => ({
  MapContainer: ({
    children,
    gestureHandling,
    scrollWheelZoom,
  }: {
    children: React.ReactNode;
    gestureHandling?: boolean;
    scrollWheelZoom?: boolean;
  }) => (
    <div
      data-testid="map-container"
      data-gesture-handling={String(gestureHandling)}
      data-scroll-wheel-zoom={String(scrollWheelZoom)}
    >
      {children}
    </div>
  ),
  GeoJSON: () => null,
  useMap: () => mockMap,
}));

vi.mock('@krozamdev/overlapping-marker-spiderfier', () => ({
  default: vi.fn().mockImplementation(function OverlappingMarkerSpiderfier() {
    const instance = {
      markers: [] as L.Marker[],
      addMarker: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      clearMarkers: vi.fn(),
      unspiderfy: vi.fn(),
    };
    instance.addMarker.mockImplementation((marker: L.Marker) => {
      instance.markers.push(marker);
      return instance;
    });
    mockOmsInstances.push(instance);
    return instance;
  }),
}));

vi.mock('../../../components/map/BasemapSwitcherControl', () => ({
  BasemapSwitcherControl: () => <div data-testid="basemap-switcher" />,
}));

const mockResultsWithCentroid: GeoDocument[] = [
  {
    id: 'res-1',
    type: 'document',
    attributes: {
      ogm: {
        id: 'res-1',
        dct_title_s: 'Result One',
        dcat_centroid: '42.36,-71.09',
      },
    },
  },
  {
    id: 'res-2',
    type: 'document',
    attributes: {
      ogm: {
        id: 'res-2',
        dct_title_s: 'Result Two',
        dcat_centroid: '40.71,-74.00',
      },
    },
  },
];

const mockOverlappingResults: GeoDocument[] = [
  mockResultsWithCentroid[0],
  {
    id: 'res-overlap',
    type: 'document',
    attributes: {
      ogm: {
        id: 'res-overlap',
        dct_title_s: 'Overlapping Result',
        dcat_centroid: '42.36,-71.09',
      },
    },
  },
];

// US locations (for refit-on-results-change test)
const mockResultsUS: GeoDocument[] = [
  {
    id: 'us-1',
    type: 'document',
    attributes: {
      ogm: {
        id: 'us-1',
        dct_title_s: 'US Result',
        dcat_centroid: '41.88,-87.62',
      },
    },
  },
];

// France/Europe locations (for refit-on-results-change test)
const mockResultsFrance: GeoDocument[] = [
  {
    id: 'fr-1',
    type: 'document',
    attributes: {
      ogm: {
        id: 'fr-1',
        dct_title_s: 'Paris Result',
        dcat_centroid: '48.85,2.35',
      },
    },
  },
];

const mockResultsWithGeometryOnly: GeoDocument[] = [
  {
    id: 'res-geom',
    type: 'document',
    attributes: {
      ogm: {
        id: 'res-geom',
        dct_title_s: 'Geometry Only',
      },
    },
    meta: {
      ui: {
        viewer: {
          geometry: {
            type: 'Point',
            coordinates: [-87.62, 41.88],
          },
        },
      },
    },
  },
];

const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>
    <MapProvider>{children}</MapProvider>
  </MemoryRouter>
);

function MapStateProbe() {
  const { hoveredResourceId, hoveredResourceSource, selectedResourceId } =
    useMapContext();
  return (
    <div
      data-testid="map-state"
      data-hovered-resource-id={hoveredResourceId ?? ''}
      data-hovered-resource-source={hoveredResourceSource ?? ''}
      data-selected-resource-id={selectedResourceId ?? ''}
    />
  );
}

describe('MapResultView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockOmsInstances.length = 0;
    mockFlyToBounds.mockClear();
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  describe('rendering', () => {
    it('renders map container with results', async () => {
      render(
        <TestWrapper>
          <MapResultView results={mockResultsWithCentroid} />
        </TestWrapper>
      );

      expect(await screen.findByTestId('map-container')).toBeInTheDocument();
      expect(await screen.findByTestId('basemap-switcher')).toBeInTheDocument();
    });

    it('enables command/control gesture handling for scroll zoom', async () => {
      render(
        <TestWrapper>
          <MapResultView results={mockResultsWithCentroid} />
        </TestWrapper>
      );

      const map = await screen.findByTestId('map-container');
      expect(map).toHaveAttribute('data-gesture-handling', 'true');
      expect(map).toHaveAttribute('data-scroll-wheel-zoom', 'true');
    });

    it('shows "No mappable results" when no pins', () => {
      render(
        <TestWrapper>
          <MapResultView
            results={[
              {
                id: 'no-geom',
                type: 'document',
                attributes: {
                  ogm: {
                    id: 'no-geom',
                    dct_title_s: 'No geometry',
                  },
                },
              },
            ]}
          />
        </TestWrapper>
      );

      expect(
        screen.getByText('No mappable results found in this page.')
      ).toBeInTheDocument();
    });

    it('renders numbered map pins with upright labels', async () => {
      render(
        <TestWrapper>
          <MapResultView
            results={mockResultsWithCentroid}
            resultStartIndex={11}
          />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(mockOmsInstances[0]?.markers).toHaveLength(2);
      });

      const icon = mockOmsInstances[0].markers[0].options.icon as L.DivIcon;
      const iconHtml = String(icon.options.html);
      expect(iconHtml).toContain('>11</span>');
      expect(iconHtml).toContain('rotate(-45deg)');
      expect(iconHtml).not.toContain('translateX(-50%) rotate(45deg)');
    });

    it('keeps the spiderfier stable while a marker is hovered and selected', async () => {
      render(
        <TestWrapper>
          <MapResultView results={mockResultsWithCentroid} />
          <MapStateProbe />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(mockOmsInstances[0]?.markers).toHaveLength(2);
      });
      const oms = mockOmsInstances[0];
      const marker = oms.markers[0];
      const mapState = screen.getByTestId('map-state');

      act(() => marker.fire('mouseover'));
      expect(mapState).toHaveAttribute('data-hovered-resource-id', 'res-1');
      expect(mapState).toHaveAttribute('data-hovered-resource-source', 'map');

      act(() => marker.fire('click'));
      expect(mapState).toHaveAttribute('data-selected-resource-id', 'res-1');
      expect(mockOmsInstances).toHaveLength(1);
      expect(oms.clearMarkers).not.toHaveBeenCalled();

      act(() => marker.fire('mouseout'));
      expect(mapState).toHaveAttribute('data-hovered-resource-id', 'res-1');
      expect(mapState).toHaveAttribute('data-hovered-resource-source', 'map');

      act(() => marker.fire('click'));
      expect(mapState).toHaveAttribute('data-selected-resource-id', '');
      expect(mapState).toHaveAttribute('data-hovered-resource-id', '');
      expect(mapState).toHaveAttribute('data-hovered-resource-source', '');
      expect(mockOmsInstances).toHaveLength(1);
      expect(oms.clearMarkers).not.toHaveBeenCalled();
    });

    it('keeps collapsed overlapping markers stable until click', async () => {
      render(
        <TestWrapper>
          <MapResultView results={mockOverlappingResults} />
          <MapStateProbe />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(mockOmsInstances[0]?.markers).toHaveLength(2);
      });
      const marker = mockOmsInstances[0].markers[0];
      const mapState = screen.getByTestId('map-state');
      const fire = vi.spyOn(marker, 'fire');
      const setIcon = vi.spyOn(marker, 'setIcon');

      act(() => marker.fire('mouseover'));
      expect(fire).not.toHaveBeenCalledWith('click');
      expect(setIcon).not.toHaveBeenCalled();
      expect(mapState).toHaveAttribute('data-hovered-resource-id', '');

      act(() => marker.fire('click'));
      expect(mapState).toHaveAttribute('data-selected-resource-id', '');

      marker._omsData = {
        usualPosition: marker.getLatLng(),
        leg: {} as L.Polyline,
      };
      act(() => marker.fire('mouseover'));
      expect(mapState).toHaveAttribute('data-hovered-resource-id', 'res-1');
    });

    it('accepts highlightedResourceId and highlightedGeometry', async () => {
      render(
        <TestWrapper>
          <MapResultView
            results={mockResultsWithCentroid}
            highlightedResourceId="res-1"
            highlightedGeometry='{"type":"Point","coordinates":[-71.09,42.36]}'
          />
        </TestWrapper>
      );

      expect(await screen.findByTestId('map-container')).toBeInTheDocument();
    });

    it('adds dashed extent overlay for MultiPolygon (same as resource view LocationMap)', async () => {
      const multiPolygonJson = JSON.stringify({
        type: 'MultiPolygon',
        coordinates: [
          [
            [
              [-75.6, 39.8],
              [-75.8, 39.7],
              [-80.5, 39.7],
              [-80.5, 42.3],
              [-75.6, 39.8],
            ],
          ],
        ],
      });
      render(
        <TestWrapper>
          <MapResultView
            results={mockResultsWithCentroid}
            highlightedResourceId="res-1"
            highlightedGeometry={multiPolygonJson}
          />
        </TestWrapper>
      );

      // HighlightOverlayController adds geoJSON layer + dashed rectangle for MultiPolygon
      await waitFor(() => {
        expect(mockMap.addLayer.mock.calls.length).toBeGreaterThanOrEqual(2);
      });
    });
  });

  describe('map refit on results change', () => {
    it('refits map when search results change (e.g. facet filter applied)', async () => {
      const { rerender } = render(
        <TestWrapper>
          <MapResultView results={mockResultsFrance} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(mockFlyToBounds).toHaveBeenCalledTimes(1);
      });

      rerender(
        <TestWrapper>
          <MapResultView results={mockResultsUS} />
        </TestWrapper>
      );

      // Should refit again when results change
      await waitFor(() => {
        expect(mockFlyToBounds).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('centroid resolution', () => {
    it('renders pins for results with dcat_centroid', async () => {
      render(
        <TestWrapper>
          <MapResultView results={mockResultsWithCentroid} />
        </TestWrapper>
      );

      expect(await screen.findByTestId('map-container')).toBeInTheDocument();
      expect(screen.queryByText('No mappable results')).not.toBeInTheDocument();
    });

    it('renders pins for results with geometry fallback (no centroid)', async () => {
      render(
        <TestWrapper>
          <MapResultView results={mockResultsWithGeometryOnly} />
        </TestWrapper>
      );

      expect(await screen.findByTestId('map-container')).toBeInTheDocument();
      expect(screen.queryByText('No mappable results')).not.toBeInTheDocument();
    });
  });
});

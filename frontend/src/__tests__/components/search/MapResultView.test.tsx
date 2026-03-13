import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { MapProvider } from '../../../context/MapContext';
import { MapResultView } from '../../../components/search/MapResultView.client';
import type { GeoDocument } from '../../../types/api';

const mockFlyToBounds = vi.fn();
const mockMap = {
  flyToBounds: mockFlyToBounds,
  openPopup: vi.fn(),
  addLayer: vi.fn(),
  removeLayer: vi.fn(),
  hasLayer: vi.fn().mockReturnValue(false),
  eachLayer: vi.fn(),
};

vi.mock('leaflet/dist/leaflet.css', () => ({}));
vi.mock('react-leaflet', () => ({
  MapContainer: ({
    children,
  }: {
    children: React.ReactNode;
  }) => <div data-testid="map-container">{children}</div>,
  GeoJSON: () => null,
  useMap: () => mockMap,
}));

vi.mock('@krozamdev/overlapping-marker-spiderfier', () => ({
  default: vi.fn().mockImplementation(() => ({
    addMarker: vi.fn(),
    addListener: vi.fn(),
    clearMarkers: vi.fn(),
    unspiderfy: vi.fn(),
  })),
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

describe('MapResultView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

      expect(screen.getByTestId('map-container')).toBeInTheDocument();
      expect(screen.getByTestId('basemap-switcher')).toBeInTheDocument();
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

    it('accepts resultStartIndex for numbered pins', () => {
      render(
        <TestWrapper>
          <MapResultView
            results={mockResultsWithCentroid}
            resultStartIndex={11}
          />
        </TestWrapper>
      );

      expect(screen.getByTestId('map-container')).toBeInTheDocument();
    });

    it('accepts highlightedResourceId and highlightedGeometry', () => {
      render(
        <TestWrapper>
          <MapResultView
            results={mockResultsWithCentroid}
            highlightedResourceId="res-1"
            highlightedGeometry='{"type":"Point","coordinates":[-71.09,42.36]}'
          />
        </TestWrapper>
      );

      expect(screen.getByTestId('map-container')).toBeInTheDocument();
    });

    it('adds dashed extent overlay for MultiPolygon (same as resource view LocationMap)', () => {
      const multiPolygonJson = JSON.stringify({
        type: 'MultiPolygon',
        coordinates: [
          [[[-75.6, 39.8], [-75.8, 39.7], [-80.5, 39.7], [-80.5, 42.3], [-75.6, 39.8]]],
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
      const addLayerCalls = mockMap.addLayer.mock.calls.length;
      expect(addLayerCalls).toBeGreaterThanOrEqual(2);
    });
  });

  describe('map refit on results change', () => {
    it('refits map when search results change (e.g. facet filter applied)', () => {
      const { rerender } = render(
        <TestWrapper>
          <MapResultView results={mockResultsFrance} />
        </TestWrapper>
      );

      expect(mockFlyToBounds).toHaveBeenCalledTimes(1);

      rerender(
        <TestWrapper>
          <MapResultView results={mockResultsUS} />
        </TestWrapper>
      );

      // Should refit again when results change
      expect(mockFlyToBounds).toHaveBeenCalledTimes(2);
    });
  });

  describe('centroid resolution', () => {
    it('renders pins for results with dcat_centroid', () => {
      render(
        <TestWrapper>
          <MapResultView results={mockResultsWithCentroid} />
        </TestWrapper>
      );

      expect(screen.getByTestId('map-container')).toBeInTheDocument();
      expect(screen.queryByText('No mappable results')).not.toBeInTheDocument();
    });

    it('renders pins for results with geometry fallback (no centroid)', () => {
      render(
        <TestWrapper>
          <MapResultView results={mockResultsWithGeometryOnly} />
        </TestWrapper>
      );

      expect(screen.getByTestId('map-container')).toBeInTheDocument();
      expect(screen.queryByText('No mappable results')).not.toBeInTheDocument();
    });
  });
});

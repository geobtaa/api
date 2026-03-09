import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { MapProvider } from '../../../context/MapContext';
import { MapResultView } from '../../../components/search/MapResultView.client';
import type { GeoDocument } from '../../../types/api';

vi.mock('leaflet/dist/leaflet.css', () => ({}));
vi.mock('react-leaflet', () => ({
  MapContainer: ({
    children,
  }: {
    children: React.ReactNode;
  }) => <div data-testid="map-container">{children}</div>,
  GeoJSON: () => null,
  useMap: () => ({
    flyToBounds: vi.fn(),
    openPopup: vi.fn(),
    addLayer: vi.fn(),
    removeLayer: vi.fn(),
    eachLayer: vi.fn(),
  }),
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

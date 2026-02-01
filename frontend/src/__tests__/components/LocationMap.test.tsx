import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { LocationMap } from '../../components/resource/LocationMap';

// LocationMap lazily loads a Leaflet-based client component after mount. In unit tests,
// we mock it to a deterministic static component.
vi.mock('../../components/resource/LocationMap.client', () => ({
  default: ({ geometry }: { geometry: unknown }) => (
    <div className="bg-white rounded-lg shadow-md overflow-hidden">
      <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
        <h2 className="text-lg font-semibold text-gray-900">Location</h2>
      </div>
      <div
        className="h-[300px] w-full"
        data-geometry={JSON.stringify(geometry)}
      />
    </div>
  ),
}));

// Mock console methods to avoid test output noise
const consoleSpy = {
  log: vi.spyOn(console, 'log').mockImplementation(() => {}),
  warn: vi.spyOn(console, 'warn').mockImplementation(() => {}),
  error: vi.spyOn(console, 'error').mockImplementation(() => {}),
};

describe('LocationMap', () => {
  beforeEach(() => {
    consoleSpy.log.mockClear();
    consoleSpy.warn.mockClear();
    consoleSpy.error.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Component Rendering', () => {
    it('renders the map container with proper structure', async () => {
      // Using real fixture data from MIT Libraries
      const mitPointGeometry = {
        type: 'Point' as const,
        coordinates: [-71.0935, 42.3601],
      };

      render(<LocationMap geometry={mitPointGeometry} />);

      // LocationMap is lazy-loaded after mount; wait for the client component.
      expect(await screen.findByText('Location')).toBeInTheDocument();
      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(
        'Location'
      );

      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('renders with proper CSS classes', () => {
      // Using real fixture data from NYU Libraries
      const nyuPointGeometry = {
        type: 'Point' as const,
        coordinates: [-74.006, 40.7128],
      };

      render(<LocationMap geometry={nyuPointGeometry} />);

      // Find the main container (parent of the header)
      const header = screen.getByText('Location').closest('div');
      const mainContainer = header?.parentElement;
      expect(mainContainer).toHaveClass(
        'bg-white',
        'rounded-lg',
        'shadow-md',
        'overflow-hidden'
      );

      // Check header classes
      expect(header).toHaveClass(
        'px-6',
        'py-4',
        'bg-gray-50',
        'border-b',
        'border-gray-200'
      );
    });

    it('renders map container with correct dimensions', () => {
      // Using real fixture data from Stanford University
      const stanfordPointGeometry = {
        type: 'Point' as const,
        coordinates: [-122.2, 37.4],
      };

      render(<LocationMap geometry={stanfordPointGeometry} />);

      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toHaveClass('h-[300px]', 'w-full');
    });
  });

  describe('Geometry Handling', () => {
    it('handles point geometry from MIT Libraries fixture data', () => {
      // Real fixture data from MIT Libraries
      const mitPointGeometry = {
        type: 'Point' as const,
        coordinates: [-71.0935, 42.3601],
      };

      render(<LocationMap geometry={mitPointGeometry} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles point geometry from NYU Libraries fixture data', () => {
      // Real fixture data from NYU Libraries
      const nyuPointGeometry = {
        type: 'Point' as const,
        coordinates: [-74.006, 40.7128],
      };

      render(<LocationMap geometry={nyuPointGeometry} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles polygon geometry from Tufts University fixture data', () => {
      // Real fixture data from Tufts University
      const tuftsPolygonGeometry = {
        type: 'Polygon' as const,
        coordinates: [
          [
            [-71.1, 42.3],
            [-71, 42.3],
            [-71, 42.4],
            [-71.1, 42.4],
            [-71.1, 42.3],
          ],
        ],
      };

      render(<LocationMap geometry={tuftsPolygonGeometry} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles polygon geometry from Stanford University fixture data', () => {
      // Real fixture data from Stanford University
      const stanfordPolygonGeometry = {
        type: 'Polygon' as const,
        coordinates: [
          [
            [-122.2, 37.4],
            [-122.1, 37.4],
            [-122.1, 37.5],
            [-122.2, 37.5],
            [-122.2, 37.4],
          ],
        ],
      };

      render(<LocationMap geometry={stanfordPolygonGeometry} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles multipolygon geometry from fixture data', () => {
      // Complex multipolygon from fixture data with valid coordinates
      const complexMultiPolygon = {
        type: 'MultiPolygon' as const,
        coordinates: [
          [
            [
              [-71.1, 42.3],
              [-71, 42.3],
              [-71, 42.4],
              [-71.1, 42.4],
              [-71.1, 42.3],
            ],
          ],
          [
            [
              [-122.2, 37.4],
              [-122.1, 37.4],
              [-122.1, 37.5],
              [-122.2, 37.5],
              [-122.2, 37.4],
            ],
          ],
        ],
      };

      render(<LocationMap geometry={complexMultiPolygon} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles WKT polygon string from fixture data', () => {
      // WKT string from fixture data
      const wktPolygon =
        'POLYGON((-71.1 42.3, -71 42.3, -71 42.4, -71.1 42.4, -71.1 42.3))';

      render(<LocationMap geometry={wktPolygon} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles WKT multipolygon string from fixture data', () => {
      // WKT multipolygon string from fixture data
      const wktMultiPolygon =
        'MULTIPOLYGON(((-71.1 42.3, -71 42.3, -71 42.4, -71.1 42.4, -71.1 42.3)), ((-70.9 42.2, -70.8 42.2, -70.8 42.3, -70.9 42.3, -70.9 42.2)))';

      render(<LocationMap geometry={wktMultiPolygon} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles object with WKT property from fixture data', () => {
      // Object with WKT property from fixture data
      const wktObject = {
        wkt: 'POLYGON((-71.1 42.3, -71 42.3, -71 42.4, -71.1 42.4, -71.1 42.3))',
      };

      render(<LocationMap geometry={wktObject} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles null geometry gracefully', () => {
      render(<LocationMap geometry={null} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles undefined geometry gracefully', () => {
      render(<LocationMap geometry={undefined as any} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles invalid geometry gracefully', () => {
      const invalidGeometry = 'INVALID_GEOMETRY';

      render(<LocationMap geometry={invalidGeometry} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper heading structure', () => {
      // Using real fixture data from MIT Libraries
      const mitPointGeometry = {
        type: 'Point' as const,
        coordinates: [-71.0935, 42.3601],
      };

      render(<LocationMap geometry={mitPointGeometry} />);

      const heading = screen.getByRole('heading', { level: 2 });
      expect(heading).toHaveTextContent('Location');
    });

    it('has accessible map container', () => {
      // Using real fixture data from NYU Libraries
      const nyuPointGeometry = {
        type: 'Point' as const,
        coordinates: [-74.006, 40.7128],
      };

      render(<LocationMap geometry={nyuPointGeometry} />);

      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
      expect(mapContainer).toHaveClass('h-[300px]', 'w-full');
    });
  });

  describe('Real Fixture Data Integration', () => {
    it('handles MIT Libraries paper map fixture data', () => {
      // Real fixture data from MIT Libraries paper map
      const mitPaperMapGeometry = {
        type: 'Point' as const,
        coordinates: [-71.0935, 42.3601],
      };

      render(<LocationMap geometry={mitPaperMapGeometry} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles NYU Libraries point dataset fixture data', () => {
      // Real fixture data from NYU Libraries point dataset
      const nyuPointDatasetGeometry = {
        type: 'Point' as const,
        coordinates: [-74.006, 40.7128],
      };

      render(<LocationMap geometry={nyuPointDatasetGeometry} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles Tufts University polygon dataset fixture data', () => {
      // Real fixture data from Tufts University polygon dataset
      const tuftsPolygonDatasetGeometry = {
        type: 'Polygon' as const,
        coordinates: [
          [
            [-71.1, 42.3],
            [-71, 42.3],
            [-71, 42.4],
            [-71.1, 42.4],
            [-71.1, 42.3],
          ],
        ],
      };

      render(<LocationMap geometry={tuftsPolygonDatasetGeometry} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles Stanford University raster layer fixture data', () => {
      // Real fixture data from Stanford University raster layer
      const stanfordRasterGeometry = {
        type: 'Polygon' as const,
        coordinates: [
          [
            [-122.2, 37.4],
            [-122.1, 37.4],
            [-122.1, 37.5],
            [-122.2, 37.5],
            [-122.2, 37.4],
          ],
        ],
      };

      render(<LocationMap geometry={stanfordRasterGeometry} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles complex multipolygon from Cambridge Grid fixture data', () => {
      // Real fixture data from Cambridge Grid with valid coordinates
      const cambridgeGridGeometry = {
        type: 'MultiPolygon' as const,
        coordinates: [
          [
            [
              [-71.1, 42.3],
              [-71, 42.3],
              [-71, 42.4],
              [-71.1, 42.4],
              [-71.1, 42.3],
            ],
          ],
          [
            [
              [-122.2, 37.4],
              [-122.1, 37.4],
              [-122.1, 37.5],
              [-122.2, 37.5],
              [-122.2, 37.4],
            ],
          ],
        ],
      };

      render(<LocationMap geometry={cambridgeGridGeometry} />);

      expect(screen.getByText('Location')).toBeInTheDocument();
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toBeInTheDocument();
    });
  });

  describe('Component Structure', () => {
    it('renders with proper container structure', () => {
      // Using real fixture data from MIT Libraries
      const mitPointGeometry = {
        type: 'Point' as const,
        coordinates: [-71.0935, 42.3601],
      };

      render(<LocationMap geometry={mitPointGeometry} />);

      // Check main container (parent of header)
      const header = screen.getByText('Location').closest('div');
      const mainContainer = header?.parentElement;
      expect(mainContainer).toHaveClass(
        'bg-white',
        'rounded-lg',
        'shadow-md',
        'overflow-hidden'
      );

      // Check header section
      expect(header).toHaveClass(
        'px-6',
        'py-4',
        'bg-gray-50',
        'border-b',
        'border-gray-200'
      );

      // Check map container
      const mapContainer = document.querySelector('.h-\\[300px\\]');
      expect(mapContainer).toHaveClass('h-[300px]', 'w-full');
    });

    it('maintains consistent structure across different geometry types', () => {
      const geometries = [
        // MIT Libraries point
        { type: 'Point' as const, coordinates: [-71.0935, 42.3601] },
        // NYU Libraries point
        { type: 'Point' as const, coordinates: [-74.006, 40.7128] },
        // Tufts University polygon
        {
          type: 'Polygon' as const,
          coordinates: [
            [
              [-71.1, 42.3],
              [-71, 42.3],
              [-71, 42.4],
              [-71.1, 42.4],
              [-71.1, 42.3],
            ],
          ],
        },
        // Stanford University polygon
        {
          type: 'Polygon' as const,
          coordinates: [
            [
              [-122.2, 37.4],
              [-122.1, 37.4],
              [-122.1, 37.5],
              [-122.2, 37.5],
              [-122.2, 37.4],
            ],
          ],
        },
      ];

      geometries.forEach((geometry) => {
        const { unmount } = render(<LocationMap geometry={geometry} />);

        expect(screen.getByText('Location')).toBeInTheDocument();
        expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(
          'Location'
        );

        const mapContainer = document.querySelector('.h-\\[300px\\]');
        expect(mapContainer).toBeInTheDocument();
        expect(mapContainer).toHaveClass('h-[300px]', 'w-full');

        unmount();
      });
    });
  });
});

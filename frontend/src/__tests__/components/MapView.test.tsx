// IMPORTANT: keep Leaflet mocks at module top-level so Vitest can hoist them before any imports.
vi.mock('leaflet/dist/leaflet.css', () => ({}));
vi.mock('leaflet', () => ({
  default: {
    map: vi.fn(() => ({
      setView: vi.fn().mockReturnThis(),
      eachLayer: vi.fn(),
      removeLayer: vi.fn(),
      addLayer: vi.fn(),
      fitBounds: vi.fn(),
      remove: vi.fn(),
    })),
    tileLayer: vi.fn(() => ({
      addTo: vi.fn().mockReturnThis(),
    })),
    geoJSON: vi.fn(() => ({
      getBounds: vi.fn().mockReturnValue({
        getNorthEast: vi.fn().mockReturnValue({ lat: 45, lng: -90 }),
        getSouthWest: vi.fn().mockReturnValue({ lat: 40, lng: -95 }),
      }),
      addTo: vi.fn().mockReturnThis(),
    })),
    rectangle: vi.fn(() => ({
      addTo: vi.fn().mockReturnThis(),
      getBounds: vi.fn().mockReturnValue({
        extend: vi.fn().mockReturnThis(),
      }),
    })),
    latLngBounds: vi.fn(() => ({
      extend: vi.fn().mockReturnThis(),
    })),
    GeoJSON: class MockGeoJSON {},
  },
}));

import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { MapView } from '../../components/search/MapView';
import { MapProvider } from '../../context/MapContext';
import type { GeoDocument } from '../../types/api';

// Real fixture data from the fixtures page
const mockFixtureData: GeoDocument[] = [
  {
    id: 'mit-001145244',
    type: 'document',
    attributes: {
      ogm: {
        id: 'mit-001145244',
        dct_title_s: 'Nondigitized paper map with library catalog link',
        dct_description_sm: ['A historical paper map from MIT collections'],
        dct_temporal_sm: ['1950'],
        dc_publisher_sm: ['MIT Libraries'],
        gbl_resourceClass_sm: ['Paper Maps'],
      },
    },
    meta: {
      ui: {
        thumbnail_url: 'https://example.com/thumbnail1.jpg',
        viewer: {
          geometry: {
            type: 'Point',
            coordinates: [-71.0935, 42.3601],
          },
        },
      },
    },
  },
  {
    id: 'nyu-2451-34564',
    type: 'document',
    attributes: {
      ogm: {
        id: 'nyu-2451-34564',
        dct_title_s: 'Point dataset with WMS and WFS',
        dct_description_sm: ['A point dataset with web mapping services'],
        dct_temporal_sm: ['2020'],
        dc_publisher_sm: ['NYU Libraries'],
        gbl_resourceClass_sm: ['Point Data'],
      },
    },
    meta: {
      ui: {
        thumbnail_url: null,
        viewer: {
          geometry: {
            type: 'Point',
            coordinates: [-74.006, 40.7128],
          },
        },
      },
    },
  },
];

// Test wrapper component
const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <MemoryRouter>
    <MapProvider>{children}</MapProvider>
  </MemoryRouter>
);

describe('MapView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset console.log mock
    vi.spyOn(console, 'log').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Basic Rendering', () => {
    it('renders the map container', () => {
      render(
        <TestWrapper>
          <MapView results={[]} />
        </TestWrapper>
      );

      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();
      expect(mapContainer).toHaveClass('w-full', 'rounded-lg', 'shadow-md');
    });

    it('renders with sticky positioning', () => {
      render(
        <TestWrapper>
          <MapView results={[]} />
        </TestWrapper>
      );

      const stickyContainer = document.querySelector('.sticky');
      expect(stickyContainer).toBeInTheDocument();
      expect(stickyContainer).toHaveClass('top-[88px]');
    });

    it('has proper container structure', () => {
      render(
        <TestWrapper>
          <MapView results={mockFixtureData} />
        </TestWrapper>
      );

      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();
      // The ref is a React ref, not a DOM attribute, so we just check the element exists
      expect(mapContainer).toBeTruthy();
    });

    it('maintains proper CSS classes for responsive design', () => {
      render(
        <TestWrapper>
          <MapView results={mockFixtureData} />
        </TestWrapper>
      );

      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toHaveClass(
        'h-[calc(100vh-120px)]',
        'w-full',
        'rounded-lg',
        'shadow-md'
      );
    });
  });

  describe('Component Props', () => {
    it('accepts results prop', () => {
      render(
        <TestWrapper>
          <MapView results={mockFixtureData} />
        </TestWrapper>
      );

      // Component should render without errors
      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles empty results array', () => {
      render(
        <TestWrapper>
          <MapView results={[]} />
        </TestWrapper>
      );

      // Component should render without errors
      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles results with valid geometry', () => {
      render(
        <TestWrapper>
          <MapView results={mockFixtureData} />
        </TestWrapper>
      );

      // Component should render without errors
      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles results without geometry', () => {
      const resultsWithoutGeometry = [
        {
          id: 'no-geometry-1',
          type: 'document',
          attributes: {
            ogm: {
              id: 'no-geometry-1',
              dct_title_s: 'No geometry result 1',
              dct_description_sm: ['A result without geometry'],
              dct_temporal_sm: ['2023'],
              dc_publisher_sm: ['Test Publisher'],
              gbl_resourceClass_sm: ['Dataset'],
            },
          },
          meta: {
            ui: {
              thumbnail_url: null,
              viewer: {
                geometry: null,
              },
            },
          },
        },
      ];

      render(
        <TestWrapper>
          <MapView results={resultsWithoutGeometry} />
        </TestWrapper>
      );

      // Component should render without errors
      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles results with missing meta data', () => {
      const resultsWithMissingMeta = [
        {
          id: 'missing-meta',
          type: 'document',
          attributes: {
            ogm: {
              id: 'missing-meta',
              dct_title_s: 'Missing meta result',
              dct_description_sm: ['A result with missing meta'],
              dct_temporal_sm: ['2023'],
              dc_publisher_sm: ['Test Publisher'],
              gbl_resourceClass_sm: ['Dataset'],
            },
          },
          meta: null,
        },
      ];

      render(
        <TestWrapper>
          <MapView results={resultsWithMissingMeta} />
        </TestWrapper>
      );

      // Component should render without errors
      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles results with missing viewer data', () => {
      const resultsWithMissingViewer = [
        {
          id: 'missing-viewer',
          type: 'document',
          attributes: {
            ogm: {
              id: 'missing-viewer',
              dct_title_s: 'Missing viewer result',
              dct_description_sm: ['A result with missing viewer'],
              dct_temporal_sm: ['2023'],
              dc_publisher_sm: ['Test Publisher'],
              gbl_resourceClass_sm: ['Dataset'],
            },
          },
          meta: {
            ui: {
              thumbnail_url: null,
              viewer: null,
            },
          },
        },
      ];

      render(
        <TestWrapper>
          <MapView results={resultsWithMissingViewer} />
        </TestWrapper>
      );

      // Component should render without errors
      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles different geometry types', () => {
      const resultsWithDifferentGeometries = [
        {
          id: 'point-geometry',
          type: 'document',
          attributes: {
            ogm: {
              id: 'point-geometry',
              dct_title_s: 'Point geometry',
              dct_description_sm: ['A point result'],
              dct_temporal_sm: ['2023'],
              dc_publisher_sm: ['Test Publisher'],
              gbl_resourceClass_sm: ['Dataset'],
            },
          },
          meta: {
            ui: {
              thumbnail_url: null,
              viewer: {
                geometry: {
                  type: 'Point',
                  coordinates: [-71.0935, 42.3601],
                },
              },
            },
          },
        },
        {
          id: 'polygon-geometry',
          type: 'document',
          attributes: {
            ogm: {
              id: 'polygon-geometry',
              dct_title_s: 'Polygon geometry',
              dct_description_sm: ['A polygon result'],
              dct_temporal_sm: ['2023'],
              dc_publisher_sm: ['Test Publisher'],
              gbl_resourceClass_sm: ['Dataset'],
            },
          },
          meta: {
            ui: {
              thumbnail_url: null,
              viewer: {
                geometry: {
                  type: 'Polygon',
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
              },
            },
          },
        },
      ];

      render(
        <TestWrapper>
          <MapView results={resultsWithDifferentGeometries} />
        </TestWrapper>
      );

      // Component should render without errors
      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();
    });
  });

  describe('Context Integration', () => {
    it('works with MapProvider', () => {
      render(
        <TestWrapper>
          <MapView results={mockFixtureData} />
        </TestWrapper>
      );

      // Component should render without errors when wrapped with MapProvider
      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();
    });

    it('handles MapContext hoveredGeometry changes', () => {
      const { rerender } = render(
        <TestWrapper>
          <MapView results={mockFixtureData} />
        </TestWrapper>
      );

      // Component should render without errors
      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();

      // Rerender with different results
      rerender(
        <TestWrapper>
          <MapView results={[]} />
        </TestWrapper>
      );

      // Component should still render without errors
      expect(mapContainer).toBeInTheDocument();
    });
  });

  describe('Performance', () => {
    it('logs performance metrics', () => {
      render(
        <TestWrapper>
          <MapView results={mockFixtureData} />
        </TestWrapper>
      );

      // Check that console.log was called (performance logging)
      expect(console.log).toHaveBeenCalled();
    });

    it('handles component unmounting', () => {
      const { unmount } = render(
        <TestWrapper>
          <MapView results={mockFixtureData} />
        </TestWrapper>
      );

      // Component should unmount without errors
      expect(() => unmount()).not.toThrow();
    });
  });

  describe('Accessibility', () => {
    it('has proper container structure for screen readers', () => {
      render(
        <TestWrapper>
          <MapView results={mockFixtureData} />
        </TestWrapper>
      );

      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toBeInTheDocument();

      // Container should have proper structure
      const stickyContainer = document.querySelector('.sticky');
      expect(stickyContainer).toBeInTheDocument();
    });

    it('maintains proper CSS classes for responsive design', () => {
      render(
        <TestWrapper>
          <MapView results={mockFixtureData} />
        </TestWrapper>
      );

      const mapContainer = document.querySelector(
        '.h-\\[calc\\(100vh-120px\\)\\]'
      );
      expect(mapContainer).toHaveClass(
        'h-[calc(100vh-120px)]',
        'w-full',
        'rounded-lg',
        'shadow-md'
      );
    });
  });
});

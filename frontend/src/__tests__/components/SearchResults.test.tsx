import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import { axeWithWCAG22 } from '../../test-utils/axe';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router';
import { SearchResults } from '../../components/SearchResults';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { MapProvider } from '../../context/MapContext';
import { BookmarkProvider } from '../../context/BookmarkContext';
import type { GeoDocument } from '../../types/api';

vi.mock('../../services/analytics', () => ({
  scheduleAnalyticsBatch: vi.fn(),
}));

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
        gbl_indexYear_im: [1950],
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
        gbl_indexYear_im: [2020],
      },
    },
    meta: {
      ui: {
        thumbnail_url: null, // Test case with no thumbnail
        viewer: {
          geometry: {
            type: 'Point',
            coordinates: [-74.006, 40.7128],
          },
        },
      },
    },
  },
  {
    id: 'tufts-cambridgegrid100-04',
    type: 'document',
    attributes: {
      ogm: {
        id: 'tufts-cambridgegrid100-04',
        dct_title_s: 'Polygon dataset with WFS, WMS, and FGDC metadata',
        dct_description_sm: ['A comprehensive polygon dataset'],
        dct_temporal_sm: ['2019', '2020'],
        dc_publisher_sm: ['Tufts University', 'Cambridge Grid'],
        gbl_resourceClass_sm: ['Polygon Data'],
        gbl_indexYear_im: [2019, 2020],
      },
    },
    meta: {
      ui: {
        thumbnail_url: 'https://example.com/thumbnail3.jpg',
        viewer: {
          geometry: {
            type: 'Polygon',
            coordinates: [
              [
                [-71.1, 42.3],
                [-71.0, 42.3],
                [-71.0, 42.4],
                [-71.1, 42.4],
                [-71.1, 42.3],
              ],
            ],
          },
        },
      },
    },
  },
  {
    id: 'stanford-dp018hs9766',
    type: 'document',
    attributes: {
      ogm: {
        id: 'stanford-dp018hs9766',
        dct_title_s: 'Restricted raster layer with WMS and metadata',
        dct_description_sm: ['A restricted access raster dataset'],
        dct_temporal_sm: ['2021'],
        dc_publisher_sm: ['Stanford University'],
        gbl_resourceClass_sm: ['Raster Data'],
        gbl_indexYear_im: [2021],
      },
    },
    meta: {
      ui: {
        thumbnail_url: 'https://example.com/thumbnail4.jpg',
        viewer: {
          geometry: {
            type: 'Point',
            coordinates: [-122.1697, 37.4275],
          },
        },
      },
    },
  },
]; // End of mockFixtureData

// Mock BookmarkButton to avoid context provider requirement
vi.mock('../../components/BookmarkButton', () => ({
  BookmarkButton: () => <button>Bookmark</button>,
}));

// Mock useBookmarks hook
vi.mock('../../context/BookmarkContext', () => ({
  useBookmarks: () => ({
    isBookmarked: () => false, // Default to false for tests
  }),
  BookmarkProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

// Test wrapper component
const TestWrapper = ({ children }: { children: React.ReactNode }) => (
  <BrowserRouter>
    <ApiProvider>
      <DebugProvider>
        <MapProvider>
          <BookmarkProvider>{children}</BookmarkProvider>
        </MapProvider>
      </DebugProvider>
    </ApiProvider>
  </BrowserRouter>
);

describe('SearchResults Component', () => {
  beforeEach(() => {
    vi.spyOn(console, 'log').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Loading State', () => {
    it('displays loading spinner when isLoading is true', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={[]}
            isLoading={true}
            totalResults={0}
            currentPage={1}
          />
        </TestWrapper>
      );

      // Check for the loading spinner element
      const spinner = document.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });

    it('does not display loading spinner when isLoading is false', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={[]}
            isLoading={false}
            totalResults={0}
            currentPage={1}
          />
        </TestWrapper>
      );

      const spinner = document.querySelector('.animate-spin');
      expect(spinner).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('displays "No results found" when results array is empty', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={[]}
            isLoading={false}
            totalResults={0}
            currentPage={1}
          />
        </TestWrapper>
      );

      expect(screen.getByText('No results found')).toBeInTheDocument();
    });
  });

  describe('Result Rendering', () => {
    it('renders year and resource class in conjoined pill', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={mockFixtureData}
            isLoading={false}
            totalResults={4}
            currentPage={1}
          />
        </TestWrapper>
      );
      // First fixture has gbl_indexYear_im: [1950], gbl_resourceClass_sm: ['Paper Maps']
      const pill = screen
        .getByText(/1950/)
        .closest('[data-testid="result-card-pill"]');
      expect(pill).toBeInTheDocument();
      expect(pill).toHaveTextContent('1950');
      expect(pill).toHaveTextContent('Paper Maps');
      expect(pill).toHaveClass('bg-[#003c5b]', 'text-white');
    });

    it('renders all search results', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={mockFixtureData}
            isLoading={false}
            totalResults={4}
            currentPage={1}
          />
        </TestWrapper>
      );

      // Check that all fixture titles are rendered
      expect(
        screen.getByText('Nondigitized paper map with library catalog link')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Point dataset with WMS and WFS')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Polygon dataset with WFS, WMS, and FGDC metadata')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Restricted raster layer with WMS and metadata')
      ).toBeInTheDocument();
    });

    it('displays result numbers correctly', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={mockFixtureData}
            isLoading={false}
            totalResults={4}
            currentPage={1}
          />
        </TestWrapper>
      );

      // First page should show results 1-4
      expect(screen.getByText('Result 1')).toBeInTheDocument();
      expect(screen.getByText('Result 2')).toBeInTheDocument();
      expect(screen.getByText('Result 3')).toBeInTheDocument();
      expect(screen.getByText('Result 4')).toBeInTheDocument();
    });

    it('displays result numbers correctly for page 2', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={mockFixtureData}
            isLoading={false}
            totalResults={4}
            currentPage={2}
            perPage={10}
          />
        </TestWrapper>
      );

      // Page 2 should show results 11-14 (10 per page)
      expect(screen.getByText('Result 11')).toBeInTheDocument();
      expect(screen.getByText('Result 12')).toBeInTheDocument();
      expect(screen.getByText('Result 13')).toBeInTheDocument();
      expect(screen.getByText('Result 14')).toBeInTheDocument();
    });

    it('displays visible result number before title (e.g. 1. Title)', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={mockFixtureData}
            isLoading={false}
            totalResults={4}
            currentPage={1}
            perPage={10}
          />
        </TestWrapper>
      );

      // First result should have "1." before the title
      const firstTitle = screen.getByText(
        'Nondigitized paper map with library catalog link'
      );
      expect(firstTitle.closest('article')).toHaveTextContent('1.');
    });

    it('displays result numbers in compact (map) variant', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={mockFixtureData.slice(0, 2)}
            isLoading={false}
            totalResults={4}
            currentPage={1}
            perPage={10}
            variant="compact"
          />
        </TestWrapper>
      );

      expect(screen.getByText('1.')).toBeInTheDocument();
      expect(screen.getByText('2.')).toBeInTheDocument();
    });

    it('uses viewer geometry for hover display (not bbox) when available', () => {
      const polygonCoords = [
        [-97, 49],
        [-87, 49],
        [-87, 43],
        [-97, 43],
        [-97, 49],
      ];
      const resultsWithGeometry: GeoDocument[] = [
        {
          id: 'polygon-result',
          type: 'document',
          attributes: {
            ogm: {
              id: 'polygon-result',
              dct_title_s: 'Result with complex geometry',
              locn_geometry:
                'POLYGON((-97 49, -87 49, -87 43, -97 43, -97 49))',
            },
          },
          meta: {
            ui: {
              thumbnail_url: 'https://example.com/thumb.jpg',
              viewer: {
                geometry: {
                  type: 'Polygon',
                  coordinates: [polygonCoords],
                },
              },
            },
          },
        },
      ];
      render(
        <TestWrapper>
          <SearchResults
            results={resultsWithGeometry}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );
      const article = screen.getByRole('article');
      const dataGeom = article.getAttribute('data-geom');
      expect(dataGeom).not.toBe('');
      const parsed = JSON.parse(dataGeom!);
      expect(parsed.type).toBe('Polygon');
      expect(parsed.coordinates[0]).toHaveLength(5);
      // meta.ui.viewer.geometry (same source as resource page LocationMap)
      const lons = parsed.coordinates[0].map((c: number[]) => c[0]);
      expect(Math.min(...lons)).toBe(-97);
      expect(Math.max(...lons)).toBe(-87);
    });

    it('uses MultiPolygon viewer geometry for hover (same as resource view, with dashed extent)', () => {
      const multi: GeoJSON.MultiPolygon = {
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
      };
      const resultsWithMulti: GeoDocument[] = [
        {
          id: 'multipolygon-result',
          type: 'document',
          attributes: {
            ogm: {
              id: 'multipolygon-result',
              dct_title_s: 'Shipping Fairways [Pennsylvania]',
              locn_geometry:
                'MultiPolygon(((-75.6 39.8, -75.8 39.7, -80.5 39.7, -80.5 42.3, -75.6 39.8)))',
            },
          },
          meta: {
            ui: {
              thumbnail_url: 'https://example.com/thumb.jpg',
              viewer: { geometry: multi },
            },
          },
        },
      ];
      render(
        <TestWrapper>
          <SearchResults
            results={resultsWithMulti}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );
      const article = screen.getByRole('article');
      const dataGeom = article.getAttribute('data-geom');
      expect(dataGeom).not.toBe('');
      const parsed = JSON.parse(dataGeom!);
      expect(parsed.type).toBe('MultiPolygon');
      expect(parsed.coordinates).toHaveLength(1);
      expect(parsed.coordinates[0][0]).toHaveLength(5);
      const lons = parsed.coordinates[0][0].map((c: number[]) => c[0]);
      expect(Math.min(...lons)).toBe(-80.5);
      expect(Math.max(...lons)).toBe(-75.6);
    });

    it('uses perPage for result numbering', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={mockFixtureData}
            isLoading={false}
            totalResults={20}
            currentPage={2}
            perPage={5}
          />
        </TestWrapper>
      );

      // Page 2 with 5 per page: results 6-9
      expect(screen.getByText('Result 6')).toBeInTheDocument();
      expect(screen.getByText('Result 9')).toBeInTheDocument();
    });
  });

  describe('Thumbnail Handling', () => {
    it('displays thumbnails when available', () => {
      const { container } = render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[0]]} // First fixture has thumbnail
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const thumbnail = container.querySelector(
        'img[src="https://example.com/thumbnail1.jpg"]'
      );
      expect(thumbnail).toBeInTheDocument();
      expect(thumbnail).toHaveAttribute('alt', '');
    });

    it('falls back to the backend thumbnail endpoint when thumbnail_url is not available', () => {
      const { container } = render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[1]]} // Second fixture has no thumbnail
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const thumbnail = container.querySelector(
        'img[src="/thumbnails/nyu-2451-34564"]'
      );
      expect(thumbnail).toBeInTheDocument();
      expect(thumbnail).toHaveAttribute('alt', '');
    });

    it('uses the list fallback asset when thumbnail_url is the generic resource thumbnail endpoint', () => {
      const genericThumbnailResult: GeoDocument = {
        ...mockFixtureData[1],
        meta: {
          ui: {
            thumbnail_url:
              'http://localhost:8000/api/v1/resources/nyu-2451-34564/thumbnail',
            viewer: {
              geometry: {
                type: 'Point',
                coordinates: [-74.006, 40.7128],
              },
            },
          },
        },
      };

      const { container } = render(
        <TestWrapper>
          <SearchResults
            results={[genericThumbnailResult]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const thumbnail = container.querySelector(
        'img[src="/thumbnails/nyu-2451-34564"]'
      );
      expect(thumbnail).toBeInTheDocument();
    });

    it('routes raw bridge thumbnail assets through the backend thumbnail endpoint', () => {
      const bridgeThumbnailResult: GeoDocument = {
        ...mockFixtureData[1],
        meta: {
          ui: {
            thumbnail_url:
              'https://geobtaa-assets-prod.s3.us-east-2.amazonaws.com/store/asset/test/huge-image.jpg',
            viewer: {
              geometry: {
                type: 'Point',
                coordinates: [-74.006, 40.7128],
              },
            },
          },
        },
      };

      const { container } = render(
        <TestWrapper>
          <SearchResults
            results={[bridgeThumbnailResult]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const thumbnail = container.querySelector(
        'img[src="/thumbnails/nyu-2451-34564"]'
      );
      expect(thumbnail).toBeInTheDocument();
      expect(thumbnail).toHaveAttribute('alt', '');
    });

    it('preserves immutable API thumbnail assets for direct browser fetching', () => {
      const imageHash =
        'e7810cca426f65fa9e5e25124ca1b213b6c54deec0901c88805558faa7e25639';
      const directHashThumbnailResult: GeoDocument = {
        ...mockFixtureData[1],
        meta: {
          ui: {
            thumbnail_url: `http://localhost:8000/api/v1/thumbnails/${imageHash}`,
            viewer: {
              geometry: {
                type: 'Point',
                coordinates: [-74.006, 40.7128],
              },
            },
          },
        },
      };

      const { container } = render(
        <TestWrapper>
          <SearchResults
            results={[directHashThumbnailResult]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const thumbnail = container.querySelector(
        `img[src="/api/v1/thumbnails/${imageHash}"]`
      );
      expect(thumbnail).toBeInTheDocument();
    });
  });

  describe('Content Display', () => {
    it('displays descriptions when available', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[0]]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      expect(
        screen.getByText('A historical paper map from MIT collections')
      ).toBeInTheDocument();
    });

    it('displays temporal information when available', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[0]]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      // Year appears in conjoined pill (1950 · Paper Maps)
      expect(screen.getByText(/1950/)).toBeInTheDocument();
    });

    it('displays multiple temporal values correctly', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[2]]} // Has multiple temporal values
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      // Index year appears in conjoined pill (2019 · Polygon Data)
      expect(screen.getByText(/2019/)).toBeInTheDocument();
    });

    it('displays publisher information when available', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[0]]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      expect(screen.getByText('MIT Libraries')).toBeInTheDocument();
    });

    it('displays multiple publishers correctly', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[2]]} // Has multiple publishers
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      expect(
        screen.getByText('Tufts University, Cambridge Grid')
      ).toBeInTheDocument();
    });
  });

  describe('Links and Navigation', () => {
    it('creates correct links to resource pages', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[0]]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const link = screen.getByRole('link', {
        name: /nondigitized paper map/i,
      });
      expect(link).toHaveAttribute('href', '/resources/mit-001145244');
    });

    it('passes correct state to resource page links', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={mockFixtureData}
            isLoading={false}
            totalResults={4}
            currentPage={1}
          />
        </TestWrapper>
      );

      const link = screen.getByRole('link', {
        name: /nondigitized paper map/i,
      });
      expect(link).toBeInTheDocument();
      // Note: Testing the state object would require more complex setup
    });
  });

  describe('Map Integration', () => {
    it('sets geometry data attribute for map integration', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[0]]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const article = screen.getByRole('article');
      expect(article).toHaveAttribute('data-geom');

      const geometryData = JSON.parse(
        article.getAttribute('data-geom') || '{}'
      );
      expect(geometryData).toEqual({
        type: 'Point',
        coordinates: [-71.0935, 42.3601],
      });
    });

    it('handles mouse enter events for map highlighting', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[0]]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const article = screen.getByRole('article');
      await user.hover(article);

      // The hover event should trigger setHoveredGeometry
      // This would be tested more thoroughly with integration tests
    });

    it('handles mouse leave events for map highlighting', async () => {
      const user = userEvent.setup();

      render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[0]]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const article = screen.getByRole('article');
      await user.hover(article);
      await user.unhover(article);

      // The unhover event should clear the hovered geometry
    });
  });

  describe('Bookmark Integration', () => {
    it('renders bookmark buttons for each result', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={mockFixtureData}
            isLoading={false}
            totalResults={4}
            currentPage={1}
          />
        </TestWrapper>
      );

      // Should have 4 bookmark buttons (one for each result)
      const bookmarkButtons = screen.getAllByRole('button');
      expect(bookmarkButtons).toHaveLength(4);
    });
  });

  describe('Debug Mode', () => {
    it('shows debug information when debug mode is enabled', () => {
      // This would require setting up the debug context to show details
      // For now, we'll test that the component renders without errors
      render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[0]]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      expect(
        screen.getByText('Nondigitized paper map with library catalog link')
      ).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('uses the backend thumbnail endpoint when thumbnail_url is missing', () => {
      const missingThumbnailResult: GeoDocument = {
        id: 'missing-thumb-test',
        type: 'document',
        attributes: {
          ogm: {
            id: 'missing-thumb-test',
            dct_title_s: 'Missing Thumbnail Test',
            gbl_resourceClass_sm: ['Websites'],
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
      };

      const { container } = render(
        <TestWrapper>
          <SearchResults
            results={[missingThumbnailResult]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const thumbnail = container.querySelector(
        'img[src="/thumbnails/missing-thumb-test"]'
      );
      expect(thumbnail).toHaveAttribute(
        'src',
        '/thumbnails/missing-thumb-test'
      );
      expect(thumbnail).toHaveAttribute('alt', '');
    });

    it('handles results with missing attributes gracefully', () => {
      const incompleteResult: GeoDocument = {
        id: 'incomplete-test',
        type: 'document',
        attributes: {
          ogm: {
            id: 'incomplete-test',
            dct_title_s: 'Test Title',
            // Missing other ogm fields is fine
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
      };

      render(
        <TestWrapper>
          <SearchResults
            results={[incompleteResult]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      expect(screen.getByText('Test Title')).toBeInTheDocument();
    });

    it('handles results with null geometry', () => {
      const noGeometryResult: GeoDocument = {
        id: 'no-geometry-test',
        type: 'document',
        attributes: {
          ogm: { id: 'no-geometry-test', dct_title_s: 'No Geometry Test' },
        },
        meta: {
          ui: {
            thumbnail_url: null,
            viewer: {
              geometry: null,
            },
          },
        },
      };

      render(
        <TestWrapper>
          <SearchResults
            results={[noGeometryResult]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const article = screen.getByRole('article');
      expect(article).toHaveAttribute('data-geom', '');
    });

    it('handles results with non-string title attributes', () => {
      const nonStringTitleResult: GeoDocument = {
        id: 'non-string-title',
        type: 'document',
        attributes: {
          ogm: {
            id: 'non-string-title',
            dct_title_s: 12345 as unknown as string, // Non-string title
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
      };

      render(
        <TestWrapper>
          <SearchResults
            results={[nonStringTitleResult]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      expect(screen.getByText('12345')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has no accessibility violations with results', async () => {
      const { container } = render(
        <TestWrapper>
          <SearchResults
            results={mockFixtureData}
            isLoading={false}
            totalResults={4}
            currentPage={1}
          />
        </TestWrapper>
      );
      const results = await axeWithWCAG22(container);
      expect(results).toHaveNoViolations();
    });

    it('has no accessibility violations when empty', async () => {
      const { container } = render(
        <TestWrapper>
          <SearchResults
            results={[]}
            isLoading={false}
            totalResults={0}
            currentPage={1}
          />
        </TestWrapper>
      );
      const results = await axeWithWCAG22(container);
      expect(results).toHaveNoViolations();
    });

    it('has proper ARIA roles and labels', () => {
      render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[0]]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      expect(screen.getByRole('article')).toBeInTheDocument();
      expect(screen.getByRole('link')).toBeInTheDocument();
      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('marks result images as decorative', () => {
      const { container } = render(
        <TestWrapper>
          <SearchResults
            results={[mockFixtureData[0]]}
            isLoading={false}
            totalResults={1}
            currentPage={1}
          />
        </TestWrapper>
      );

      const image = container.querySelector(
        'img[src="https://example.com/thumbnail1.jpg"]'
      );
      expect(image).toBeInTheDocument();
      expect(image).toHaveAttribute('alt', '');
    });
  });
});

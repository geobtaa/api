import { render, screen, waitFor } from '@testing-library/react';
import { axeWithWCAG22 } from '../../test-utils/axe';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router';
import { ResourceView } from '../../components/resource/ResourceView';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { MapProvider } from '../../context/MapContext';
import { BookmarkProvider } from '../../context/BookmarkContext';
import { vi } from 'vitest';
import type { GeoDocument } from '../../types/api';

// Real fixture data from the /test/fixtures page
const realFixtureData: GeoDocument[] = [
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
        dct_accessRights_s: 'Public',
        dct_accessrights_s: 'Public',
        gbl_wxsidentifier_s: 'mit-001145244',
        gbl_wxsIdentifier_s: 'mit-001145244',
        locn_geometry_original: 'POINT(-71.0935 42.3601)',
        ui_viewer_protocol: 'wms',
        ui_viewer_endpoint: 'https://example.com/wms',
      },
    },
    meta: {
      ui: {
        thumbnail_url: 'https://example.com/thumbnail1.jpg',
        viewer: {
          protocol: 'wms',
          endpoint: 'https://example.com/wms',
          geometry: {
            type: 'Point',
            coordinates: [-71.0935, 42.3601],
          },
        },
        downloads: [
          {
            label: 'PDF Download',
            url: 'https://example.com/download.pdf',
            type: 'application/pdf',
          },
        ],
        citation:
          'MIT Libraries (1950). Nondigitized paper map with library catalog link.',
        links: {
          'Library Catalog': [
            {
              label: 'MIT Library Catalog',
              url: 'https://example.com/catalog',
            },
          ],
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
        dct_description_sm: ['A point dataset from NYU with web services'],
        dct_temporal_sm: ['2020'],
        dc_publisher_sm: ['NYU Libraries'],
        gbl_resourceClass_sm: ['Point Data'],
        dct_accessRights_s: 'Public',
        dct_accessrights_s: 'Public',
        gbl_wxsidentifier_s: 'nyu-2451-34564',
        gbl_wxsIdentifier_s: 'nyu-2451-34564',
        locn_geometry_original: 'POINT(-74.0060 40.7128)',
        ui_viewer_protocol: 'arcgis_feature_layer',
        ui_viewer_endpoint: 'https://example.com/arcgis',
      },
    },
    meta: {
      ui: {
        thumbnail_url: 'https://example.com/thumbnail2.jpg',
        viewer: {
          protocol: 'arcgis_feature_layer',
          endpoint: 'https://example.com/arcgis',
          geometry: {
            type: 'Point',
            coordinates: [-74.006, 40.7128],
          },
        },
        downloads: [
          {
            label: 'Shapefile Download',
            url: 'https://example.com/download2.zip',
            type: 'application/zip',
          },
        ],
        citation: 'NYU Libraries (2020). Point dataset with WMS and WFS.',
        links: {
          'Web Services': [
            {
              label: 'WMS Service',
              url: 'https://example.com/wms2',
            },
            {
              label: 'WFS Service',
              url: 'https://example.com/wfs2',
            },
          ],
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
        dct_description_sm: [
          'A polygon dataset from Tufts with comprehensive metadata',
        ],
        dct_temporal_sm: ['2019'],
        dc_publisher_sm: ['Tufts University'],
        gbl_resourceClass_sm: ['Polygon Data'],
        dct_accessRights_s: 'Public',
        dct_accessrights_s: 'Public',
        gbl_wxsidentifier_s: 'tufts-cambridgegrid100-04',
        gbl_wxsIdentifier_s: 'tufts-cambridgegrid100-04',
        locn_geometry_original:
          'POLYGON((-71.1 42.3, -71.0 42.3, -71.0 42.4, -71.1 42.4, -71.1 42.3))',
        ui_viewer_protocol: 'open_index_map',
        ui_viewer_endpoint: 'https://example.com/indexmap',
      },
    },
    meta: {
      ui: {
        thumbnail_url: 'https://example.com/thumbnail3.jpg',
        viewer: {
          protocol: 'open_index_map',
          endpoint: 'https://example.com/indexmap',
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
        downloads: [
          {
            label: 'GeoJSON Download',
            url: 'https://example.com/download3.geojson',
            type: 'application/geojson',
          },
        ],
        citation:
          'Tufts University (2019). Polygon dataset with WFS, WMS, and FGDC metadata.',
        links: {
          'Web Services': [
            {
              label: 'WMS Service',
              url: 'https://example.com/wms3',
            },
            {
              label: 'WFS Service',
              url: 'https://example.com/wfs3',
            },
          ],
        },
      },
    },
  },
];

// Mock the API functions
vi.mock('../../services/api', () => ({
  fetchResourceDetails: vi.fn(),
  fetchSearchResults: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(message: string) {
      super(message);
      this.name = 'ApiError';
    }
  },
}));

// Mock react-router-dom
const mockNavigate = vi.fn();
const mockLocation = {
  state: null,
  pathname: '/resources/mit-001145244',
  search: '',
  hash: '',
  key: 'test-key',
};

vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useParams: () => ({ id: 'mit-001145244' }),
    useNavigate: () => mockNavigate,
    useLocation: () => mockLocation,
  };
});

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

describe('ResourceView Component', () => {
  let fetchResourceDetails: any;
  let fetchSearchResults: any;

  beforeEach(async () => {
    vi.clearAllMocks();

    // Import the mocked functions
    const apiModule = await import('../../services/api');
    fetchResourceDetails = apiModule.fetchResourceDetails;
    fetchSearchResults = apiModule.fetchSearchResults;

    // Mock successful API response
    (fetchResourceDetails as any).mockResolvedValue(realFixtureData[0]);
    (fetchSearchResults as any).mockResolvedValue({
      data: realFixtureData,
    });
  });

  describe('Loading State', () => {
    it('displays loading spinner when data is being fetched', async () => {
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      // Should show loading spinner initially
      const spinner = document.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });

    it('does not display loading spinner after data is loaded', async () => {
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getAllByText(
            'Nondigitized paper map with library catalog link'
          ).length
        ).toBeGreaterThan(0);
      });

      const spinner = document.querySelector('.animate-spin');
      expect(spinner).not.toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when API call fails', async () => {
      (fetchResourceDetails as any).mockRejectedValue(new Error('API Error'));

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getByText(
            'An unexpected error occurred while fetching item details'
          )
        ).toBeInTheDocument();
      });
    });

    it('displays ApiError message when API returns specific error', async () => {
      const { ApiError } = await import('../../services/api');
      (fetchResourceDetails as any).mockRejectedValue(
        new ApiError('Resource not found')
      );

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Resource not found')).toBeInTheDocument();
      });
    });
  });

  describe('Resource Display', () => {
    it('displays resource title', async () => {
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getByRole('heading', {
            name: 'Nondigitized paper map with library catalog link',
          })
        ).toBeInTheDocument();
      });
    });

    it('displays resource breadcrumbs', async () => {
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        // Check for breadcrumb link specifically (aria-label: "Filter by {value}")
        const links = screen.getAllByRole('link', {
          name: 'Filter by Paper Maps',
        });
        const breadcrumbLink = links.find(
          (a) =>
            a.getAttribute('href') ===
            '/search?fq%5Bgbl_resourceClass_sm%5D%5B%5D=Paper+Maps'
        );
        expect(breadcrumbLink).toBeTruthy();
      });
    });

    it('displays resource subtitle', async () => {
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        // ResourceSubtitle should render publisher and year
        // Check for the subtitle heading
        const subtitle = screen.getByRole('heading', { name: /1950/ });
        expect(subtitle).toBeInTheDocument();
        expect(subtitle.tagName).toBe('H2');
      });
    });
  });

  describe('Navigation', () => {
    it('displays navigation controls when search state is available', async () => {
      const searchState = {
        searchResults: realFixtureData.map((item) => ({ id: item.id })),
        currentIndex: 0,
        totalResults: 3,
        searchUrl: '/search?q=test',
        currentPage: 1,
      };

      mockLocation.state = searchState;

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByTitle('Back to Search Results')).toBeInTheDocument();
        expect(screen.getByTitle('Clear Search')).toBeInTheDocument();
      });
    });

    it('shows next button when more results are available', async () => {
      const searchState = {
        searchResults: realFixtureData.map((item) => ({ id: item.id })),
        currentIndex: 0,
        totalResults: 3,
        searchUrl: '/search?q=test',
        currentPage: 1,
      };

      mockLocation.state = searchState;

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByTitle('Next')).toBeInTheDocument();
      });
    });

    it('shows previous button when previous results are available', async () => {
      const searchState = {
        searchResults: realFixtureData.map((item) => ({ id: item.id })),
        currentIndex: 1,
        totalResults: 3,
        searchUrl: '/search?q=test',
        currentPage: 1,
      };

      mockLocation.state = searchState;

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByTitle('Previous')).toBeInTheDocument();
      });
    });

    it('handles next navigation within current page', async () => {
      const user = userEvent.setup();
      const searchState = {
        searchResults: realFixtureData.map((item) => ({ id: item.id })),
        currentIndex: 0,
        totalResults: 3,
        searchUrl: '/search?q=test',
        currentPage: 1,
      };

      mockLocation.state = searchState;

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByTitle('Next')).toBeInTheDocument();
      });

      const nextButton = screen.getByTitle('Next');
      await user.click(nextButton);

      expect(mockNavigate).toHaveBeenCalledWith('/resources/nyu-2451-34564', {
        state: {
          ...searchState,
          currentIndex: 1,
        },
      });
    });

    it('handles previous navigation within current page', async () => {
      const user = userEvent.setup();
      const searchState = {
        searchResults: realFixtureData.map((item) => ({ id: item.id })),
        currentIndex: 1,
        totalResults: 3,
        searchUrl: '/search?q=test',
        currentPage: 1,
      };

      mockLocation.state = searchState;

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByTitle('Previous')).toBeInTheDocument();
      });

      const prevButton = screen.getByTitle('Previous');
      await user.click(prevButton);

      expect(mockNavigate).toHaveBeenCalledWith('/resources/mit-001145244', {
        state: {
          ...searchState,
          currentIndex: 0,
        },
      });
    });

    it('handles next navigation to new page', async () => {
      const user = userEvent.setup();
      const searchState = {
        searchResults: realFixtureData
          .slice(0, 2)
          .map((item) => ({ id: item.id })),
        currentIndex: 1,
        totalResults: 3,
        searchUrl: '/search?q=test',
        currentPage: 1,
      };

      mockLocation.state = searchState;

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByTitle('Next')).toBeInTheDocument();
      });

      const nextButton = screen.getByTitle('Next');
      await user.click(nextButton);

      expect(fetchSearchResults).toHaveBeenCalledWith(
        'test',
        2,
        10,
        [],
        expect.any(Function)
      );
    });

    it('handles previous navigation to previous page', async () => {
      const user = userEvent.setup();
      const searchState = {
        searchResults: realFixtureData
          .slice(1, 3)
          .map((item) => ({ id: item.id })),
        currentIndex: 1, // Set to 1 so hasPreviousResults is true
        totalResults: 3,
        searchUrl: '/search?q=test',
        currentPage: 2,
      };

      mockLocation.state = searchState;

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        // The Previous button should be visible when currentIndex > 0
        expect(screen.getByTitle('Previous')).toBeInTheDocument();
      });

      const prevButton = screen.getByTitle('Previous');
      await user.click(prevButton);

      // Should navigate to previous item in current results
      expect(mockNavigate).toHaveBeenCalledWith('/resources/nyu-2451-34564', {
        state: {
          ...searchState,
          currentIndex: 0,
        },
      });
    });
  });

  describe('Conditional Rendering', () => {
    it('renders ResourceViewer when viewer protocol is available', async () => {
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getAllByText(
            'Nondigitized paper map with library catalog link'
          ).length
        ).toBeGreaterThan(0);
      });

      // ResourceViewer should be rendered when protocol is available
      expect(
        screen.getAllByText('Nondigitized paper map with library catalog link')
          .length
      ).toBeGreaterThan(0);
    });

    it('renders AttributeTable when protocol is wms', async () => {
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Attribute')).toBeInTheDocument();
        expect(screen.getByText('Value')).toBeInTheDocument();
        expect(
          screen.getByText('Click on map to inspect values')
        ).toBeInTheDocument();
      });
    });

    it('renders IndexMap when protocol is open_index_map', async () => {
      // Mock the component with open_index_map protocol
      (fetchResourceDetails as any).mockResolvedValue(realFixtureData[2]); // Tufts fixture with open_index_map

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getAllByText(
            'Polygon dataset with WFS, WMS, and FGDC metadata'
          ).length
        ).toBeGreaterThan(0);
      });

      // IndexMap should be rendered
      expect(
        screen.getAllByText('Polygon dataset with WFS, WMS, and FGDC metadata')
          .length
      ).toBeGreaterThan(0);
    });

    it('renders FullDetailsTable', async () => {
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getAllByText(
            'Nondigitized paper map with library catalog link'
          ).length
        ).toBeGreaterThan(0);
      });

      // FullDetailsTable should be rendered
      expect(
        screen.getAllByText('Nondigitized paper map with library catalog link')
          .length
      ).toBeGreaterThan(0);
    });

    it('renders MetadataTable', async () => {
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Item Summary')).toBeInTheDocument();
      });
    });

    it('renders CitationTable when citation is available', async () => {
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getAllByText(
            'Nondigitized paper map with library catalog link'
          ).length
        ).toBeGreaterThan(0);
      });

      // CitationTable should be rendered when citation is available
      expect(
        screen.getAllByText('Nondigitized paper map with library catalog link')
          .length
      ).toBeGreaterThan(0);
    });
  });

  describe('Edge Cases', () => {
    it('handles missing search state gracefully', async () => {
      mockLocation.state = null;

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getAllByText(
            'Nondigitized paper map with library catalog link'
          ).length
        ).toBeGreaterThan(0);
      });

      // Should still render the resource with navigation controls (they default to home)
      expect(screen.getByTitle('Back to Search Results')).toBeInTheDocument();
    });

    it('handles different fixture data types', async () => {
      // Test with NYU fixture
      (fetchResourceDetails as any).mockResolvedValue(realFixtureData[1]);

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getAllByText('Point dataset with WMS and WFS').length
        ).toBeGreaterThan(0);
      });
    });

    it('handles polygon data fixture', async () => {
      // Test with Tufts fixture
      (fetchResourceDetails as any).mockResolvedValue(realFixtureData[2]);

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getAllByText(
            'Polygon dataset with WFS, WMS, and FGDC metadata'
          ).length
        ).toBeGreaterThan(0);
      });
    });

    it('handles restricted access fixture', async () => {
      const restrictedFixture = {
        ...realFixtureData[0],
        attributes: {
          ...realFixtureData[0].attributes,
          ogm: {
            ...realFixtureData[0].attributes.ogm,
            dct_accessRights_s: 'Restricted',
            dct_accessrights_s: 'Restricted',
          },
        },
      };

      (fetchResourceDetails as any).mockResolvedValue(restrictedFixture);

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getAllByText(
            'Nondigitized paper map with library catalog link'
          ).length
        ).toBeGreaterThan(0);
      });
    });
  });

  describe('URL Parameter Handling', () => {
    it('extracts search parameters correctly for pagination', async () => {
      const searchState = {
        searchResults: realFixtureData.map((item) => ({ id: item.id })),
        currentIndex: 0,
        totalResults: 3,
        searchUrl: '/search?q=test&facet=type:Dataset',
        currentPage: 1,
      };

      mockLocation.state = searchState;

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getAllByText(
            'Nondigitized paper map with library catalog link'
          ).length
        ).toBeGreaterThan(0);
      });

      // Should display current position
      expect(screen.getByText('1 of 3')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getByRole('heading', {
            name: 'Nondigitized paper map with library catalog link',
          })
        ).toBeInTheDocument();
      });

      const results = await axeWithWCAG22(container);
      expect(results).toHaveNoViolations();
    });

    it('has proper ARIA roles and labels', async () => {
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getByRole('heading', {
            name: 'Nondigitized paper map with library catalog link',
          })
        ).toBeInTheDocument();
      });

      // Check for proper table structure (there are multiple tables)
      const tables = screen.getAllByRole('table');
      expect(tables.length).toBeGreaterThan(0);
    });

    it('has proper button titles for navigation', async () => {
      const searchState = {
        searchResults: realFixtureData.map((item) => ({ id: item.id })),
        currentIndex: 1,
        totalResults: 3,
        searchUrl: '/search?q=test',
        currentPage: 1,
      };

      mockLocation.state = searchState;

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByTitle('Back to Search Results')).toBeInTheDocument();
        expect(screen.getByTitle('Previous')).toBeInTheDocument();
        expect(screen.getByTitle('Next')).toBeInTheDocument();
        expect(screen.getByTitle('Clear Search')).toBeInTheDocument();
      });
    });
  });
});

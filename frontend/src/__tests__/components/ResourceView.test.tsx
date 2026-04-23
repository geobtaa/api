import { render, screen, waitFor } from '@testing-library/react';
import { axeWithWCAG22 } from '../../test-utils/axe';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { ResourceView } from '../../pages/ResourceView';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { vi } from 'vitest';
import type { GeoDocument } from '../../types/api';

vi.mock('../../services/analytics', () => ({
  scheduleAnalyticsBatch: vi.fn(),
}));

// Mock the API functions to return real fixture data
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

// Mock react-router-dom hooks
const mockNavigate = vi.fn();
const mockUseParams = vi.fn();
const mockUseLocation = vi.fn();
const mockUseNavigate = vi.fn();

vi.mock('react-router', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useParams: () => mockUseParams(),
    useLocation: () => mockUseLocation(),
    useNavigate: () => mockUseNavigate(),
  };
});

// Real fixture data from the fixtures page
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
        // Some parts of the UI still reference the legacy lowercase key.
        dct_accessrights_s: 'Public',
        gbl_wxsidentifier_s: 'mit-001145244',
        gbl_wxsIdentifier_s: 'mit-001145244',
        locn_geometry_original: 'POINT(-71.0935 42.3601)',
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
      },
    },
    meta: {
      ui: {
        thumbnail_url: 'https://example.com/thumbnail2.jpg',
        viewer: {
          protocol: 'wms',
          endpoint: 'https://example.com/wms2',
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
      },
    },
    meta: {
      ui: {
        thumbnail_url: 'https://example.com/thumbnail3.jpg',
        viewer: {
          protocol: 'wms',
          endpoint: 'https://example.com/wms3',
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
            type: 'application/geo+json',
          },
        ],
        citation:
          'Tufts University (2019). Polygon dataset with WFS, WMS, and FGDC metadata.',
        links: {
          Metadata: [
            {
              label: 'FGDC Metadata',
              url: 'https://example.com/metadata3.xml',
            },
          ],
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
        dct_description_sm: ['A restricted raster dataset from Stanford'],
        dct_temporal_sm: ['2021'],
        dc_publisher_sm: ['Stanford University'],
        gbl_resourceClass_sm: ['Raster Data'],
        dct_accessRights_s: 'Restricted',
        dct_accessrights_s: 'Restricted',
        gbl_wxsidentifier_s: 'stanford-dp018hs9766',
        gbl_wxsIdentifier_s: 'stanford-dp018hs9766',
        locn_geometry_original:
          'POLYGON((-122.2 37.4, -122.1 37.4, -122.1 37.5, -122.2 37.5, -122.2 37.4))',
      },
    },
    meta: {
      ui: {
        thumbnail_url: 'https://example.com/thumbnail4.jpg',
        viewer: {
          protocol: 'wms',
          endpoint: 'https://example.com/wms4',
          geometry: {
            type: 'Polygon',
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
        },
        downloads: [],
        citation:
          'Stanford University (2021). Restricted raster layer with WMS and metadata.',
        links: {
          Documentation: [
            {
              label: 'Usage Guidelines',
              url: 'https://example.com/usage4.pdf',
            },
          ],
        },
      },
    },
  },
];

// Use the first fixture as the default test data
const mockResourceData = realFixtureData[0];
const mockResourceWithDataDictionary: GeoDocument = {
  ...mockResourceData,
  attributes: {
    ...mockResourceData.attributes,
    b1g: {
      data_dictionaries: [
        {
          id: 1,
          friendlier_id: 'mit-001145244',
          name: 'Attributes',
          description: 'Dictionary description',
          staff_notes: null,
          tags: '',
          position: 1,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
          entries: [
            {
              id: 101,
              resource_data_dictionary_id: 1,
              friendlier_id: 'mit-001145244',
              field_name: 'parcel_id',
              field_type: 'string',
              values: null,
              definition: 'Parcel identifier',
              definition_source: 'Source',
              parent_field_name: null,
              position: 1,
              created_at: null,
              updated_at: null,
            },
          ],
        },
      ],
    },
  },
};

const mockSearchState = {
  searchResults: realFixtureData.map((fixture) => ({ id: fixture.id })),
  currentIndex: 0,
  totalResults: realFixtureData.length,
  searchUrl: '/search?q=test',
  currentPage: 1,
  absoluteIndex: 0,
};

import { HelmetProvider } from 'react-helmet-async';

// Test wrapper component
const TestWrapper = ({
  children,
  initialEntries = ['/resources/mit-001145244'],
}: {
  children: React.ReactNode;
  initialEntries?: string[];
}) => (
  <HelmetProvider>
    <MemoryRouter initialEntries={initialEntries}>
      <ApiProvider>
        <DebugProvider>{children}</DebugProvider>
      </ApiProvider>
    </MemoryRouter>
  </HelmetProvider>
);

describe('ResourceView Component', () => {
  let fetchResourceDetails: any;
  let fetchSearchResults: any;

  beforeEach(async () => {
    vi.clearAllMocks();
    const apiModule = await import('../../services/api');
    fetchResourceDetails = vi.mocked(apiModule.fetchResourceDetails);
    fetchSearchResults = vi.mocked(apiModule.fetchSearchResults);

    mockUseParams.mockReturnValue({ id: 'mit-001145244' });
    mockUseLocation.mockReturnValue({
      state: mockSearchState,
      pathname: '/resources/mit-001145244',
      search: '',
      hash: '',
      key: 'test-key',
    });
    mockUseNavigate.mockReturnValue(mockNavigate);

    // Use real fixture data instead of mocks
    fetchResourceDetails.mockImplementation((id: string) => {
      const fixture = realFixtureData.find((f) => f.id === id);
      return Promise.resolve(fixture || mockResourceData);
    });

    fetchSearchResults.mockResolvedValue({
      data: realFixtureData.slice(0, 2), // Return first 2 fixtures for pagination tests
      meta: { total: realFixtureData.length, page: 2, per_page: 10 },
      included: [],
    });
  });

  describe('Loading State', () => {
    it('displays loading spinner when data is being fetched', async () => {
      // Make the API call hang
      fetchResourceDetails.mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

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
          screen.getByRole('heading', {
            name: 'Nondigitized paper map with library catalog link',
          })
        ).toBeInTheDocument();
      });

      const spinner = document.querySelector('.animate-spin');
      expect(spinner).not.toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('displays error message when API call fails', async () => {
      const errorMessage = 'Resource not found';
      fetchResourceDetails.mockRejectedValue(new Error(errorMessage));

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
      const apiError = new ApiError('API Error: Resource not accessible');
      fetchResourceDetails.mockRejectedValue(apiError);

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getByText('API Error: Resource not accessible')
        ).toBeInTheDocument();
      });
    });
  });

  describe('No Data State', () => {
    it('displays debug message when no data is loaded', async () => {
      fetchResourceDetails.mockResolvedValue(null);

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        // Check for the debug container
        const debugContainer = document.querySelector(
          '.bg-yellow-100.border.border-yellow-400'
        );
        expect(debugContainer).toBeInTheDocument();
        expect(debugContainer).toHaveTextContent('Debug:');
        expect(debugContainer).toHaveTextContent('No data loaded yet');
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
        expect(
          screen.getByRole('heading', {
            name: 'Nondigitized paper map with library catalog link',
          })
        ).toBeInTheDocument();
      });

      // Breadcrumbs should be present (component renders them)
      expect(screen.getByText('Back')).toBeInTheDocument();
    });

    it('displays resource subtitle', async () => {
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

      // ResourceSubtitle component should be rendered - check for publisher in breadcrumbs
      expect(screen.getAllByText('Paper Maps')).toHaveLength(2);
    });
  });

  describe('Data Dictionary UI', () => {
    it('renders sidebar Data Dictionary card when dictionaries exist', async () => {
      fetchResourceDetails.mockResolvedValue(mockResourceWithDataDictionary);

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

      expect(
        screen.getByRole('button', { name: 'Data Dictionaries (1)' })
      ).toBeInTheDocument();
    });

    it('opens data dictionary modal with table content', async () => {
      fetchResourceDetails.mockResolvedValue(mockResourceWithDataDictionary);

      const user = userEvent.setup();
      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getByRole('button', { name: 'Data Dictionaries (1)' })
        ).toBeInTheDocument();
      });

      await user.click(
        screen.getByRole('button', { name: 'Data Dictionaries (1)' })
      );

      expect(screen.getByText('Data Dictionaries')).toBeInTheDocument();
      expect(screen.getByText('Attributes')).toBeInTheDocument();
      expect(screen.getByText('parcel_id')).toBeInTheDocument();
    });
  });

  describe('Navigation', () => {
    it('displays navigation controls when search state is available', async () => {
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

      expect(screen.getByText('Back')).toBeInTheDocument();
      expect(screen.getByText('Clear')).toBeInTheDocument();
      expect(screen.getByText('1 of 4')).toBeInTheDocument();
    });

    it('shows next button when more results are available', async () => {
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

      expect(screen.getByText('Next')).toBeInTheDocument();
    });

    it('shows previous button when previous results are available', async () => {
      // Set current index to 1 (not first item)
      const searchStateWithIndex = {
        ...mockSearchState,
        currentIndex: 1,
        absoluteIndex: 1,
      };
      mockUseLocation.mockReturnValue({
        state: searchStateWithIndex,
        pathname: '/resources/mit-001145244',
        search: '',
        hash: '',
        key: 'test-key',
      });

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

      expect(screen.getByText('Prev')).toBeInTheDocument();
    });

    it('handles next navigation within current page', async () => {
      const user = userEvent.setup();

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

      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      expect(mockNavigate).toHaveBeenCalledWith('/resources/nyu-2451-34564', {
        state: {
          ...mockSearchState,
          currentIndex: 1,
          absoluteIndex: 1,
        },
      });
    });

    it('handles previous navigation within current page', async () => {
      const user = userEvent.setup();

      // Set current index to 1 (not first item)
      const searchStateWithIndex = {
        ...mockSearchState,
        currentIndex: 1,
        absoluteIndex: 1,
      };
      mockUseLocation.mockReturnValue({
        state: searchStateWithIndex,
        pathname: '/resources/mit-001145244',
        search: '',
        hash: '',
        key: 'test-key',
      });

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

      const prevButton = screen.getByTitle('Previous');
      await user.click(prevButton);

      expect(mockNavigate).toHaveBeenCalledWith('/resources/mit-001145244', {
        state: {
          ...searchStateWithIndex,
          currentIndex: 0,
          absoluteIndex: 0,
        },
      });
    });

    it('handles next navigation to new page', async () => {
      const user = userEvent.setup();
      const currentPageResults = Array.from({ length: 10 }, (_, index) => ({
        id: `result-${index}`,
      }));
      currentPageResults[9] = { id: 'mit-001145244' };

      const filteredSearchState = {
        ...mockSearchState,
        searchResults: currentPageResults,
        currentIndex: 9,
        totalResults: 20,
        searchUrl:
          '/search?q=chicago&include_filters[gbl_resourceClass_sm][]=Maps',
        currentPage: 1,
        perPage: 10,
        absoluteIndex: 9,
      };
      mockUseLocation.mockReturnValue({
        state: filteredSearchState,
        pathname: '/resources/mit-001145244',
        search: '',
        hash: '',
        key: 'test-key',
      });

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

      await user.click(screen.getByText('Next'));

      expect(fetchSearchResults).toHaveBeenCalledWith(
        'chicago',
        2,
        10,
        [],
        expect.any(Function),
        undefined,
        [],
        [],
        undefined,
        expect.any(URLSearchParams)
      );

      const paginationCall = fetchSearchResults.mock.calls.find(
        (call) =>
          call[1] === 2 && call[2] === 10 && call[9] instanceof URLSearchParams
      );
      expect(paginationCall).toBeDefined();

      const sourceSearchParams = paginationCall?.[9] as URLSearchParams;
      expect(sourceSearchParams.get('q')).toBe('chicago');
      expect(
        sourceSearchParams.getAll('include_filters[gbl_resourceClass_sm][]')
      ).toEqual(['Maps']);

      expect(mockNavigate).toHaveBeenCalledWith(
        '/resources/mit-001145244',
        expect.objectContaining({
          state: expect.objectContaining({
            currentIndex: 0,
            currentPage: 2,
            absoluteIndex: 10,
            searchResults: realFixtureData.slice(0, 2),
          }),
        })
      );
    });

    it('handles previous navigation to previous page', async () => {
      const user = userEvent.setup();

      // Set to first item in current page
      const searchStateFirstItem = {
        ...mockSearchState,
        currentIndex: 0,
        absoluteIndex: 10, // Not first item overall
      };
      mockUseLocation.mockReturnValue({
        state: searchStateFirstItem,
        pathname: '/resources/mit-001145244',
        search: '',
        hash: '',
        key: 'test-key',
      });

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

      const prevButton = screen.getByTitle('Previous');
      await user.click(prevButton);

      expect(fetchSearchResults).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/resources/nyu-2451-34564', {
        state: {
          ...searchStateFirstItem,
          searchResults: realFixtureData.slice(0, 2),
          currentIndex: 1,
          currentPage: 0,
          absoluteIndex: 9,
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
          screen.getByRole('heading', {
            name: 'Nondigitized paper map with library catalog link',
          })
        ).toBeInTheDocument();
      });

      // ResourceViewer should be rendered (it's a complex component, so we check for its container)
      const viewerContainer = document.querySelector(
        '.bg-white.rounded-lg.shadow-md'
      );
      expect(viewerContainer).toBeInTheDocument();
    });

    it('renders AttributeTable when protocol is wms', async () => {
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

      expect(screen.getByText('Attribute')).toBeInTheDocument();
      expect(screen.getByText('Value')).toBeInTheDocument();
      expect(
        screen.getByText('Click on map to inspect values')
      ).toBeInTheDocument();
    });

    it('renders IndexMap when protocol is open_index_map', async () => {
      const resourceWithIndexMap = {
        ...mockResourceData,
        meta: {
          ...mockResourceData.meta,
          ui: {
            ...mockResourceData.meta?.ui,
            viewer: {
              ...mockResourceData.meta?.ui?.viewer,
              protocol: 'open_index_map',
            },
          },
        },
      };
      fetchResourceDetails.mockResolvedValue(resourceWithIndexMap);

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

      const indexMapContainer = document.querySelector('.viewer-information');
      expect(indexMapContainer).toBeInTheDocument();
    });

    it('renders LocationMap when geometry is available', async () => {
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

      // LocationMap should be rendered (it's a complex component, so we check for its presence)
      // The component should be in the sidebar
      const sidebar = document.querySelector('.lg\\:col-span-4');
      expect(sidebar).toBeInTheDocument();
    });

    it('renders DownloadsTable when downloads are available', async () => {
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

      // DownloadsTable should be rendered
      expect(screen.getByText('PDF Download')).toBeInTheDocument();
    });

    it('renders LinksTable when links are available', async () => {
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

      // LinksTable should be rendered - check for the category name
      expect(screen.getByText('Library Catalog')).toBeInTheDocument();
    });

    it('renders CitationTable when citation is available', async () => {
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

      // CitationTable should be rendered
      expect(
        screen.getByText(
          'MIT Libraries (1950). Nondigitized paper map with library catalog link.'
        )
      ).toBeInTheDocument();
    });

    it('renders FullDetailsTable', async () => {
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

      // FullDetailsTable should always be rendered
      // We can check for the presence of the component by looking for common table elements
      const tables = document.querySelectorAll('table');
      expect(tables.length).toBeGreaterThan(0);
    });
  });

  describe('Edge Cases', () => {
    it('handles missing search state gracefully', async () => {
      mockUseLocation.mockReturnValue({
        state: null,
        pathname: '/resources/mit-001145244',
        search: '',
        hash: '',
        key: 'test-key',
      });

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

      // Should still render the resource but without navigation controls
      expect(screen.queryByText('1 of 25')).not.toBeInTheDocument();
    });

    it('handles missing resource ID', async () => {
      mockUseParams.mockReturnValue({ id: undefined });

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      // Should not make API call and should show loading state
      expect(fetchResourceDetails).not.toHaveBeenCalled();
    });

    it('handles resource with minimal data', async () => {
      const minimalResource = {
        id: 'minimal-resource',
        type: 'document',
        attributes: {
          ogm: {
            id: 'minimal-resource',
            dct_title_s: 'Minimal Resource',
          },
        },
        meta: {
          ui: {
            thumbnail_url: null,
            viewer: null,
            downloads: [],
            citation: null,
            links: {},
          },
        },
      };
      fetchResourceDetails.mockResolvedValue(minimalResource);

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getByRole('heading', { name: 'Minimal Resource' })
        ).toBeInTheDocument();
      });

      // Should still render the basic structure
      expect(screen.getByTitle('Back to Search Results')).toBeInTheDocument();
    });

    it('handles different fixture data types', async () => {
      // Test with NYU point data fixture
      mockUseParams.mockReturnValue({ id: 'nyu-2451-34564' });
      fetchResourceDetails.mockImplementation((id: string) => {
        if (id === 'nyu-2451-34564') {
          return Promise.resolve(realFixtureData[1]); // NYU fixture
        }
        return Promise.resolve(mockResourceData);
      });

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getByRole('heading', {
            name: 'Point dataset with WMS and WFS',
          })
        ).toBeInTheDocument();
      });

      // Should render NYU-specific content
      expect(screen.getAllByText('Point Data')).toHaveLength(2);
      expect(screen.getByText('Web Services')).toBeInTheDocument();
    });

    it('handles polygon data fixture', async () => {
      // Test with Tufts polygon data fixture
      mockUseParams.mockReturnValue({ id: 'tufts-cambridgegrid100-04' });
      fetchResourceDetails.mockImplementation((id: string) => {
        if (id === 'tufts-cambridgegrid100-04') {
          return Promise.resolve(realFixtureData[2]); // Tufts fixture
        }
        return Promise.resolve(mockResourceData);
      });

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getByRole('heading', {
            name: 'Polygon dataset with WFS, WMS, and FGDC metadata',
          })
        ).toBeInTheDocument();
      });

      // Should render Tufts-specific content
      expect(screen.getAllByText('Polygon Data')).toHaveLength(2);
      expect(screen.getByText('Metadata')).toBeInTheDocument();
    });

    it('handles restricted access fixture', async () => {
      // Test with Stanford restricted raster fixture
      mockUseParams.mockReturnValue({ id: 'stanford-dp018hs9766' });
      fetchResourceDetails.mockImplementation((id: string) => {
        if (id === 'stanford-dp018hs9766') {
          return Promise.resolve(realFixtureData[3]); // Stanford fixture
        }
        return Promise.resolve(mockResourceData);
      });

      render(
        <TestWrapper>
          <ResourceView />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(
          screen.getByRole('heading', {
            name: 'Restricted raster layer with WMS and metadata',
          })
        ).toBeInTheDocument();
      });

      // Should render Stanford-specific content
      expect(screen.getAllByText('Raster Data')).toHaveLength(2);
      // "Documentation" appears both in the resource UI and in the global footer link;
      // assert specifically on the resource UI control.
      expect(
        screen.getByRole('button', { name: 'Documentation' })
      ).toBeInTheDocument();
    });

    it('handles navigation errors gracefully', async () => {
      // Test with a simple error scenario
      fetchResourceDetails.mockRejectedValue(new Error('Network error'));

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

      // Should show error message and not crash
      expect(
        screen.getByText(
          'An unexpected error occurred while fetching item details'
        )
      ).toBeInTheDocument();
    });
  });

  describe('URL Parameter Handling', () => {
    it('extracts search parameters correctly for pagination', async () => {
      // Test basic navigation functionality
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

      // Should show navigation controls
      expect(screen.getByText('Back')).toBeInTheDocument();
      expect(screen.getByText('Clear')).toBeInTheDocument();
      expect(screen.getByText('1 of 4')).toBeInTheDocument();
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

      expect(screen.getByRole('main')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /next/i })).toBeInTheDocument();
    });

    it('has proper button titles for navigation', async () => {
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

      expect(screen.getByTitle('Back to Search Results')).toBeInTheDocument();
      expect(screen.getByTitle('Next')).toBeInTheDocument();
      expect(screen.getByTitle('Clear Search')).toBeInTheDocument();
    });
  });
});

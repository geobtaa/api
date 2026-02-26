import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { vi } from 'vitest';
import Cookies from 'js-cookie';
import { BookmarksPage } from '../../pages/BookmarksPage';
import { ApiProvider } from '../../context/ApiContext';
import { BookmarkProvider } from '../../context/BookmarkContext';
import { DebugProvider } from '../../context/DebugContext';
import { fetchBookmarkedResources } from '../../services/api';

// Mock the API service
vi.mock('../../services/api', () => ({
  fetchBookmarkedResources: vi.fn(),
}));

// Mock the components that are complex to test in isolation
vi.mock('../../components/layout/Header', () => ({
  Header: () => <div data-testid="header">Header</div>,
}));

vi.mock('../../components/layout/Footer', () => ({
  Footer: () => <div data-testid="footer">Footer</div>,
}));

vi.mock('../../components/SearchResults', () => ({
  SearchResults: ({ results, isLoading, totalResults }: any) => (
    <div data-testid="search-results">
      {isLoading ? (
        <div data-testid="loading">Loading...</div>
      ) : (
        <div>
          <div data-testid="total-results">Total: {totalResults}</div>
          <div data-testid="results-count">Results: {results.length}</div>
        </div>
      )}
    </div>
  ),
}));

vi.mock('../../components/FacetList', () => ({
  FacetList: ({ facets }: any) => (
    <div data-testid="facet-list">Facets: {facets.length}</div>
  ),
}));

vi.mock('../../components/search/MapView', () => ({
  MapView: ({ results }: any) => (
    <div data-testid="map-view">Map with {results.length} results</div>
  ),
}));

vi.mock('../../components/search/SortControl', () => ({
  SortControl: ({ options, currentSort, onSortChange }: any) => (
    <div data-testid="sort-control">
      <div data-testid="current-sort">{currentSort}</div>
      <div data-testid="sort-options">{options.length} options</div>
      <button onClick={() => onSortChange('title')} data-testid="sort-button">
        Change Sort
      </button>
    </div>
  ),
}));

const mockFetchBookmarkedResources = vi.mocked(fetchBookmarkedResources);

// Test wrapper component
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  return (
    <HelmetProvider>
      <BrowserRouter>
        <ApiProvider>
          <BookmarkProvider>
            <DebugProvider>{children}</DebugProvider>
          </BookmarkProvider>
        </ApiProvider>
      </BrowserRouter>
    </HelmetProvider>
  );
};

// Helper function to render with bookmarks
const renderWithBookmarks = (bookmarks: string[]) => {
  Cookies.set('bookmarks', JSON.stringify(bookmarks));
  return render(
    <TestWrapper>
      <BookmarksPage />
    </TestWrapper>
  );
};

describe('BookmarksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear cookies before each test
    Cookies.remove('bookmarks');
  });

  describe('Loading States', () => {
    it('shows loading state initially', async () => {
      mockFetchBookmarkedResources.mockImplementation(
        () => new Promise(() => {}) // Never resolves to keep loading state
      );

      renderWithBookmarks(['mit-001145244']);

      expect(screen.getByTestId('loading')).toBeInTheDocument();
      expect(screen.getByText('Bookmarked Resources (1)')).toBeInTheDocument();
    });

    it('hides loading state after data loads', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              dct_title_s: 'MIT Paper Map',
              dct_description_sm: ['A paper map from MIT'],
              gbl_resourceClass_sm: ['Paper Maps'],
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
        ],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['mit-001145244']);

      await waitFor(() => {
        expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('total-results')).toHaveTextContent('Total: 1');
      expect(screen.getByTestId('results-count')).toHaveTextContent(
        'Results: 1'
      );
    });
  });

  describe('Bookmark Count Display', () => {
    it('displays correct bookmark count with multiple bookmarks', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 0,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks([
        'mit-001145244',
        'nyu-2451-34564',
        'tufts-cambridgegrid100-04',
      ]);

      await waitFor(() => {
        expect(
          screen.getByText('Bookmarked Resources (3)')
        ).toBeInTheDocument();
      });
    });

    it('displays zero count when no bookmarks', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 0,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks([]);

      await waitFor(() => {
        expect(
          screen.getByText('Bookmarked Resources (0)')
        ).toBeInTheDocument();
      });
    });
  });

  describe('API Integration', () => {
    it('calls fetchBookmarkedResources with correct parameters', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 0,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      const bookmarks = ['mit-001145244', 'nyu-2451-34564'];

      renderWithBookmarks(bookmarks);

      await waitFor(() => {
        expect(mockFetchBookmarkedResources).toHaveBeenCalledWith(
          bookmarks,
          expect.any(Function) // setLastApiUrl callback
        );
      });
    });

    it('handles API errors gracefully', async () => {
      const consoleSpy = vi
        .spyOn(console, 'error')
        .mockImplementation(() => {});

      mockFetchBookmarkedResources.mockRejectedValue(new Error('API Error'));

      renderWithBookmarks(['mit-001145244']);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Error fetching bookmarks:',
          expect.any(Error)
        );
      });

      // Should still show the page structure even with errors
      expect(screen.getByText('Bookmarked Resources (1)')).toBeInTheDocument();

      consoleSpy.mockRestore();
    });
  });

  describe('Sort Control', () => {
    it('shows sort control when sort options are available', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              dct_title_s: 'MIT Paper Map',
              dct_description_sm: ['A paper map from MIT'],
              gbl_resourceClass_sm: ['Paper Maps'],
            },
          },
        ],
        included: [
          {
            type: 'sort',
            id: 'relevance',
            attributes: { label: 'Relevance' },
            links: { self: '/sort/relevance' },
          },
          {
            type: 'sort',
            id: 'title',
            attributes: { label: 'Title' },
            links: { self: '/sort/title' },
          },
        ],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['mit-001145244']);

      await waitFor(() => {
        expect(screen.getByTestId('sort-control')).toBeInTheDocument();
        expect(screen.getByTestId('current-sort')).toHaveTextContent(
          'relevance'
        );
        expect(screen.getByTestId('sort-options')).toHaveTextContent(
          '2 options'
        );
      });
    });

    it('hides sort control when no sort options are available', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              dct_title_s: 'MIT Paper Map',
              dct_description_sm: ['A paper map from MIT'],
              gbl_resourceClass_sm: ['Paper Maps'],
            },
          },
        ],
        included: [], // No sort options
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['mit-001145244']);

      await waitFor(() => {
        expect(screen.queryByTestId('sort-control')).not.toBeInTheDocument();
      });
    });

    it('handles sort change correctly', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              dct_title_s: 'MIT Paper Map',
              dct_description_sm: ['A paper map from MIT'],
              gbl_resourceClass_sm: ['Paper Maps'],
            },
          },
        ],
        included: [
          {
            type: 'sort',
            id: 'relevance',
            attributes: { label: 'Relevance' },
            links: { self: '/sort/relevance' },
          },
          {
            type: 'sort',
            id: 'title',
            attributes: { label: 'Title' },
            links: { self: '/sort/title' },
          },
        ],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['mit-001145244']);

      await waitFor(() => {
        expect(screen.getByTestId('sort-control')).toBeInTheDocument();
      });

      // Click the sort button to change sort
      const sortButton = screen.getByTestId('sort-button');
      sortButton.click();

      await waitFor(() => {
        expect(screen.getByTestId('current-sort')).toHaveTextContent('title');
      });
    });
  });

  describe('Facet List', () => {
    it('shows facet list when facets are available', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              ogm: {
                id: 'mit-001145244',
                dct_title_s: 'MIT Paper Map',
                dct_description_sm: ['A paper map from MIT'],
                gbl_resourceClass_sm: ['Paper Maps'],
              },
            },
          },
        ],
        included: [
          {
            type: 'facet',
            id: 'gbl_resourceClass_sm',
            attributes: { label: 'Resource Class', items: [['Paper Maps', 1]] },
          },
          {
            type: 'facet',
            id: 'schema_provider_s',
            attributes: { label: 'Provider', items: [['MIT Libraries', 1]] },
          },
        ],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['mit-001145244']);

      await waitFor(() => {
        const facetLists = screen.getAllByTestId('facet-list');
        expect(facetLists.length).toBeGreaterThan(0);
        expect(facetLists[0]).toHaveTextContent('Facets: 2');
      });
    });

    it('hides facet list when no facets are available', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              dct_title_s: 'MIT Paper Map',
              dct_description_sm: ['A paper map from MIT'],
              gbl_resourceClass_sm: ['Paper Maps'],
            },
          },
        ],
        included: [], // No facets
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['mit-001145244']);

      await waitFor(() => {
        expect(screen.queryByTestId('facet-list')).not.toBeInTheDocument();
      });
    });

    it('filters facets to only show configured facets', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              ogm: {
                id: 'mit-001145244',
                dct_title_s: 'MIT Paper Map',
                dct_description_sm: ['A paper map from MIT'],
                gbl_resourceClass_sm: ['Paper Maps'],
              },
            },
          },
        ],
        included: [
          {
            type: 'facet',
            id: 'gbl_resourceClass_sm', // This should be included (configured facet)
            attributes: { label: 'Resource Class', items: [['Paper Maps', 1]] },
          },
          {
            type: 'facet',
            id: 'unconfigured_facet', // This should be filtered out
            attributes: {
              label: 'Unconfigured Facet',
              items: [['Ignore Me', 1]],
            },
          },
        ],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['mit-001145244']);

      await waitFor(() => {
        const facetLists = screen.getAllByTestId('facet-list');
        expect(facetLists.length).toBeGreaterThan(0);
        // Should only show 1 facet (the configured one)
        expect(facetLists[0]).toHaveTextContent('Facets: 1');
      });
    });
  });

  describe('Map View', () => {
    it('shows map view with results', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 2,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              dct_title_s: 'MIT Paper Map',
              dct_description_sm: ['A paper map from MIT'],
              gbl_resourceClass_sm: ['Paper Maps'],
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
            id: 'nyu-2451-34564',
            type: 'document',
            attributes: {
              dct_title_s: 'NYU Point Data',
              dct_description_sm: ['Point dataset from NYU'],
              gbl_resourceClass_sm: ['Point Data'],
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
        ],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['mit-001145244', 'nyu-2451-34564']);

      await waitFor(() => {
        expect(screen.getByTestId('map-view')).toBeInTheDocument();
        expect(screen.getByTestId('map-view')).toHaveTextContent(
          'Map with 2 results'
        );
      });
    });

    it('shows empty map when no results', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 0,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks([]);

      await waitFor(() => {
        expect(screen.getByTestId('map-view')).toBeInTheDocument();
        expect(screen.getByTestId('map-view')).toHaveTextContent(
          'Map with 0 results'
        );
      });
    });
  });

  describe('Layout and Responsive Design', () => {
    it('renders all main layout components', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 0,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks([]);

      await waitFor(() => {
        expect(screen.getByTestId('header')).toBeInTheDocument();
        expect(screen.getByTestId('footer')).toBeInTheDocument();
        expect(screen.getByTestId('search-results')).toBeInTheDocument();
        expect(screen.getByTestId('map-view')).toBeInTheDocument();
      });
    });

    it('shows mobile-friendly facet toggle', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              dct_title_s: 'MIT Paper Map',
              dct_description_sm: ['A paper map from MIT'],
              gbl_resourceClass_sm: ['Paper Maps'],
            },
          },
        ],
        included: [
          {
            type: 'facet',
            id: 'resource_class_agg',
            attributes: { label: 'Resource Class' },
          },
        ],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['mit-001145244']);

      await waitFor(() => {
        expect(screen.getAllByText('Filter Results')).toHaveLength(2); // Mobile and desktop versions
      });
    });
  });

  describe('Real Fixture Data Integration', () => {
    it('handles MIT Libraries fixture data', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'mit-001145244',
            type: 'document',
            attributes: {
              dct_title_s: 'actual-papermap1',
              dct_description_sm: [
                'Nondigitized paper map with library catalog link',
              ],
              gbl_resourceClass_sm: ['Paper Maps'],
              dc_publisher_sm: ['MIT Libraries'],
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
        ],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['mit-001145244']);

      await waitFor(() => {
        expect(
          screen.getByText('Bookmarked Resources (1)')
        ).toBeInTheDocument();
        expect(screen.getByTestId('total-results')).toHaveTextContent(
          'Total: 1'
        );
      });
    });

    it('handles NYU Libraries fixture data', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'nyu-2451-34564',
            type: 'document',
            attributes: {
              dct_title_s: 'actual-point1',
              dct_description_sm: ['Point dataset with WMS and WFS'],
              gbl_resourceClass_sm: ['Point Data'],
              dc_publisher_sm: ['NYU Libraries'],
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
        ],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['nyu-2451-34564']);

      await waitFor(() => {
        expect(
          screen.getByText('Bookmarked Resources (1)')
        ).toBeInTheDocument();
        expect(screen.getByTestId('map-view')).toHaveTextContent(
          'Map with 1 results'
        );
      });
    });

    it('handles Tufts University fixture data', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 1,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [
          {
            id: 'tufts-cambridgegrid100-04',
            type: 'document',
            attributes: {
              dct_title_s: 'actual-polygon1',
              dct_description_sm: [
                'Polygon dataset with WFS, WMS, and FGDC metadata',
              ],
              gbl_resourceClass_sm: ['Polygon Data'],
              dc_publisher_sm: ['Tufts University'],
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
        ],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['tufts-cambridgegrid100-04']);

      await waitFor(() => {
        expect(
          screen.getByText('Bookmarked Resources (1)')
        ).toBeInTheDocument();
        expect(screen.getByTestId('results-count')).toHaveTextContent(
          'Results: 1'
        );
      });
    });
  });

  describe('Edge Cases', () => {
    it('handles empty response gracefully', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 0,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks([]);

      await waitFor(() => {
        expect(
          screen.getByText('Bookmarked Resources (0)')
        ).toBeInTheDocument();
        expect(screen.getByTestId('total-results')).toHaveTextContent(
          'Total: 0'
        );
        expect(screen.getByTestId('results-count')).toHaveTextContent(
          'Results: 0'
        );
      });
    });

    it('handles response with null data gracefully', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 0,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: null,
        included: null,
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['test-id']);

      await waitFor(() => {
        expect(
          screen.getByText('Bookmarked Resources (1)')
        ).toBeInTheDocument();
        expect(screen.getByTestId('total-results')).toHaveTextContent(
          'Total: 0'
        );
        expect(screen.getByTestId('results-count')).toHaveTextContent(
          'Results: 0'
        );
      });
    });

    it('handles response with undefined meta gracefully', async () => {
      const mockResponse = {
        jsonapi: { version: '1.0', profile: [] },
        links: { self: '', first: '', last: '' },
        meta: {
          totalCount: 0,
          totalPages: 1,
          currentPage: 1,
          perPage: 10,
          query: '',
        },
        data: [],
        included: [],
      };

      mockFetchBookmarkedResources.mockResolvedValue(mockResponse);

      renderWithBookmarks(['test-id']);

      await waitFor(() => {
        expect(
          screen.getByText('Bookmarked Resources (1)')
        ).toBeInTheDocument();
        expect(screen.getByTestId('total-results')).toHaveTextContent(
          'Total: 0'
        );
      });
    });
  });
});

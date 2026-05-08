import { render, screen, waitFor, act } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { HelmetProvider } from 'react-helmet-async';
import { SearchPage } from '../../pages/SearchPage';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { fetchNominatimSearch, fetchSearchResults } from '../../services/api';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import type {
  GazetteerResponse,
  GeoDocument,
  JsonApiResponse,
} from '../../types/api';

vi.mock('../../services/analytics', () => ({
  scheduleAnalyticsBatch: vi.fn(),
  generateAnalyticsId: vi.fn(() => 'search_test_id'),
  serializeSearchParams: vi.fn(() => ({})),
}));

vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return {
    ...actual,
    fetchSearchResults: vi.fn(),
    fetchNominatimSearch: vi.fn(),
  };
});

// Mock child components to isolate SearchPage logic
vi.mock('../../components/search/GeospatialFilterMap', () => ({
  GeospatialFilterMap: () => <div data-testid="geo-filter-map">Geo Map</div>,
}));

vi.mock('../../components/search/ResourceClassFilterTabs', () => ({
  ResourceClassFilterTabs: () => (
    <div data-testid="resource-class-filter-tabs">Resource Class Tabs</div>
  ),
}));

vi.mock('../../components/SearchResults', () => ({
  SearchResults: ({ results }: { results: GeoDocument[] }) => (
    <div data-testid="search-results-list">
      {results.map((r) => (
        <div key={r.id}>List Result {r.attributes.ogm.dct_title_s}</div>
      ))}
    </div>
  ),
}));

vi.mock('../../components/search/GalleryView', () => ({
  GalleryView: ({
    results,
    currentPage,
    perPage,
  }: {
    results: GeoDocument[];
    currentPage: number;
    perPage: number;
  }) => (
    <div
      data-testid="gallery-view"
      data-current-page={currentPage}
      data-per-page={perPage}
    >
      {results.map((r) => (
        <div key={r.id}>Gallery Result {r.attributes.ogm.dct_title_s}</div>
      ))}
    </div>
  ),
}));

vi.mock('../../components/search/MapResultView', () => ({
  MapResultView: () => <div data-testid="map-result-view">Map Result View</div>,
}));

const mockResults: GeoDocument[] = Array.from({ length: 40 }, (_, i) => ({
  type: 'file',
  id: `result-${i + 1}`,
  attributes: {
    ogm: {
      dct_title_s: `Result ${i + 1}`,
      gbl_resourceClass_sm: ['Map'],
    },
    // Add other required fields if necessary
  },
  links: { self: '#' },
}));

const createMockApiResponse = (
  data: GeoDocument[],
  total = 100,
  page = 1
): JsonApiResponse => ({
  data,
  meta: {
    pages: {
      current_page: page,
      next_page: page + 1, // simplified
      prev_page: page > 1 ? page - 1 : null,
      total_pages: Math.ceil(total / 20),
      total_count: total,
    },
    totalCount: total, // SearchPage uses this
    perPage: 20,
  },
  links: { self: '', next: '', prev: '', first: '', last: '' },
  included: [],
});

const createMockGazetteerResponse = (): GazetteerResponse => ({
  jsonapi: { version: '1.1', profile: [] },
  links: { self: '' },
  meta: {
    totalCount: 0,
    totalPages: 0,
    currentPage: 1,
    perPage: 5,
    query: '',
    offset: 0,
    gazetteer: 'nominatim',
  },
  data: [],
});

const createMockResult = (id: string, title: string): GeoDocument => ({
  type: 'file',
  id,
  attributes: {
    ogm: {
      dct_title_s: title,
      gbl_resourceClass_sm: ['Map'],
    },
  },
  links: { self: '#' },
});

describe('SearchPage Logic', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchSearchResults).mockReset();
    vi.mocked(fetchNominatimSearch).mockResolvedValue(
      createMockGazetteerResponse()
    );
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ data: [] }),
    }) as unknown as typeof fetch;
    localStorage.clear();
    sessionStorage.clear();
    vi.spyOn(sessionStorage, 'getItem');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const renderWithRouter = (
    initialUrl = '/search',
    searchResults: JsonApiResponse | null = null,
    options?: { returnRouter?: boolean; clientSearchEnabled?: boolean }
  ) => {
    const routes = [
      {
        path: '/search',
        element: (
          <HelmetProvider>
            <ApiProvider>
              <DebugProvider>
                {/* MapProvider is guarded inside SearchPage, but we can wrap here too just in case context is needed outside */}
                <SearchPage
                  searchResults={searchResults}
                  isLoading={false}
                  clientSearchEnabled={options?.clientSearchEnabled}
                />
              </DebugProvider>
            </ApiProvider>
          </HelmetProvider>
        ),
      },
    ];

    const router = createMemoryRouter(routes, {
      initialEntries: [initialUrl],
    });

    const result = render(<RouterProvider router={router} />);
    return options?.returnRouter ? { ...result, router } : result;
  };

  it('renders Gallery View when view=gallery param is present', async () => {
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search?view=gallery', results);

    expect(screen.getByTestId('gallery-view')).toBeInTheDocument();
    expect(screen.queryByTestId('search-results-list')).not.toBeInTheDocument();
  });

  it('does not mount the location map by default in gallery view', async () => {
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search?view=gallery', results);

    expect(screen.queryByTestId('geo-filter-map')).not.toBeInTheDocument();
  });

  it('mounts the location map by default in map view', async () => {
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search?view=map', results);

    expect(screen.getByTestId('geo-filter-map')).toBeInTheDocument();
  });

  it('shows zero-result help and suppresses the location map when no results are available', async () => {
    const results = createMockApiResponse([], 0);
    renderWithRouter('/search?q=grassland&view=map', results);

    expect(screen.queryByTestId('geo-filter-map')).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Showing results 0-0 of 0/i)
    ).not.toBeInTheDocument();
    expect(screen.getByText('No result locations to map.')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent(
      'No search results found'
    );
    expect(
      screen.getAllByRole('link', { name: /advanced search/i })[0]
    ).toHaveAttribute('href', expect.stringContaining('showAdvanced=true'));
    expect(
      await screen.findByText('No close keyword suggestions found.')
    ).toBeInTheDocument();
    expect(
      await screen.findByText('No matching geographic areas found.')
    ).toBeInTheDocument();
  });

  it('renders Map View by default', async () => {
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search', results);

    expect(screen.getByTestId('map-result-view')).toBeInTheDocument();
    expect(screen.queryByTestId('gallery-view')).not.toBeInTheDocument();
  });

  it('hides stale client results while a new query is loading', async () => {
    const mockFetchSearchResults = vi.mocked(fetchSearchResults);
    const oldResults = createMockApiResponse(
      [createMockResult('old-result', 'Old query result')],
      1,
      1
    );
    const newResults = createMockApiResponse(
      [createMockResult('new-result', 'North Dakota result')],
      1,
      1
    );
    let resolveNewSearch!: (value: JsonApiResponse) => void;

    mockFetchSearchResults
      .mockResolvedValueOnce(oldResults)
      .mockImplementationOnce(
        () =>
          new Promise<JsonApiResponse>((resolve) => {
            resolveNewSearch = resolve;
          })
      );

    const { router } = renderWithRouter('/search?q=old', null, {
      returnRouter: true,
      clientSearchEnabled: true,
    });

    expect(
      await screen.findByText('List Result Old query result')
    ).toBeInTheDocument();

    await act(async () => {
      await router.navigate('/search?q=North+Dakota');
    });

    await waitFor(() => {
      expect(mockFetchSearchResults).toHaveBeenCalledTimes(2);
    });
    expect(
      screen.queryByText('List Result Old query result')
    ).not.toBeInTheDocument();

    await act(async () => {
      resolveNewSearch(newResults);
    });

    expect(
      await screen.findByText('List Result North Dakota result')
    ).toBeInTheDocument();
  });

  it('restores saved map view preference when URL has no view param', async () => {
    localStorage.setItem('b1g_view_preference', 'map');
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search?q=', results);

    await waitFor(() => {
      expect(screen.getByTestId('map-result-view')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('gallery-view')).not.toBeInTheDocument();
  });

  it('restores saved gallery view preference when URL has no view param', async () => {
    localStorage.setItem('b1g_view_preference', 'gallery');
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search?q=', results);

    await waitFor(() => {
      expect(screen.getByTestId('gallery-view')).toBeInTheDocument();
    });
    expect(screen.queryByTestId('search-results-list')).not.toBeInTheDocument();
    expect(screen.queryByTestId('map-result-view')).not.toBeInTheDocument();
  });

  it('restores saved list view preference when URL has no view param', async () => {
    localStorage.setItem('b1g_view_preference', 'list');
    const results = createMockApiResponse(mockResults.slice(0, 20));
    renderWithRouter('/search?q=', results);

    await waitFor(() => {
      expect(screen.getByTestId('search-results-list')).toBeInTheDocument();
      expect(screen.queryByTestId('map-result-view')).not.toBeInTheDocument();
    });
    expect(screen.queryByTestId('gallery-view')).not.toBeInTheDocument();
  });

  it('preserves bbox filter when removing facet from search constraints', async () => {
    const bboxAndMapsUrl =
      '/search?q=&view=map' +
      '&include_filters%5Bgeo%5D%5Btype%5D=bbox' +
      '&include_filters%5Bgeo%5D%5Bfield%5D=dcat_bbox' +
      '&include_filters%5Bgeo%5D%5Btop_left%5D%5Blat%5D=41.28' +
      '&include_filters%5Bgeo%5D%5Btop_left%5D%5Blon%5D=-90.76' +
      '&include_filters%5Bgeo%5D%5Bbottom_right%5D%5Blat%5D=34.59' +
      '&include_filters%5Bgeo%5D%5Bbottom_right%5D%5Blon%5D=-82.28' +
      '&include_filters%5Bgbl_resourceClass_sm%5D%5B%5D=Maps';

    const results = createMockApiResponse(mockResults.slice(0, 20));
    const { router } = renderWithRouter(bboxAndMapsUrl, results, {
      returnRouter: true,
    });

    const mapsButton = screen.getByRole('button', {
      name: /Resource Class: Maps/i,
    });
    await act(async () => {
      mapsButton.click();
    });

    const params = new URLSearchParams(router.state.location.search);
    expect(params.get('include_filters[geo][type]')).toBe('bbox');
    expect(params.get('include_filters[geo][top_left][lat]')).toBe('41.28');
    expect(params.get('include_filters[geo][bottom_right][lat]')).toBe('34.59');
    expect(params.get('include_filters[gbl_resourceClass_sm][]')).toBeNull();
  });

  it('keeps an empty q param when Clear All is clicked', async () => {
    const filteredSearchUrl =
      '/search?q=' + '&include_filters%5Bgbl_resourceClass_sm%5D%5B%5D=Maps';

    const results = createMockApiResponse(mockResults.slice(0, 20));
    const { router } = renderWithRouter(filteredSearchUrl, results, {
      returnRouter: true,
    });

    await act(async () => {
      screen.getByRole('button', { name: /clear all/i }).click();
    });

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/search');
      expect(router.state.location.search).toBe('?q=');
    });
  });

  it('displays correct pagination text for initial gallery load', async () => {
    const results = createMockApiResponse(mockResults.slice(0, 20), 100, 1);
    renderWithRouter('/search?view=gallery', results);

    // Should show 1-20
    expect(
      screen.getByText(/Showing results 1-20 of 100/i)
    ).toBeInTheDocument();
  });

  it('ignores stale gallery state and keeps Grid paginated', async () => {
    const storedState = {
      context: 'view=gallery',
      results: mockResults.slice(0, 40),
      startPage: 1,
    };
    sessionStorage.setItem('b1g_gallery_state', JSON.stringify(storedState));
    sessionStorage.setItem('b1g_gallery_restore_requested', '1');

    const serverResults = createMockApiResponse(
      mockResults.slice(0, 20),
      100,
      1
    );

    renderWithRouter('/search?view=gallery', serverResults);

    await waitFor(() => {
      expect(screen.getAllByText(/Gallery Result/)).toHaveLength(20);
    });

    expect(
      screen.getByText(/Showing results 1-20 of 100/i)
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /next page/i })
    ).toBeInTheDocument();
  });
});

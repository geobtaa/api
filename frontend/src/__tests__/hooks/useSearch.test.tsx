import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import { useSearch } from '../../hooks/useSearch';
import { ApiProvider } from '../../context/ApiContext';
import { DebugProvider } from '../../context/DebugContext';
import { fetchSearchResults } from '../../services/api';

// Mock the API function
vi.mock('../../services/api', () => ({
  fetchSearchResults: vi.fn(),
}));

// Mock console methods to avoid test output noise
const consoleSpy = {
  log: vi.spyOn(console, 'log').mockImplementation(() => {}),
  error: vi.spyOn(console, 'error').mockImplementation(() => {}),
};

// Test wrapper component
const TestWrapper = ({
  children,
  initialSearchParams: _initialSearchParams = '', // eslint-disable-line @typescript-eslint/no-unused-vars
}: {
  children: React.ReactNode;
  initialSearchParams?: string;
}) => {
  return (
    <BrowserRouter>
      <ApiProvider>
        <DebugProvider>{children}</DebugProvider>
      </ApiProvider>
    </BrowserRouter>
  );
};

// Helper to render hook with initial search params
const renderUseSearch = (initialSearchParams = '') => {
  // Set initial URL with search params
  if (initialSearchParams) {
    window.history.pushState({}, '', `/?${initialSearchParams}`);
  } else {
    window.history.pushState({}, '', '/');
  }

  return renderHook(() => useSearch(), {
    wrapper: ({ children }) => (
      <TestWrapper initialSearchParams={initialSearchParams}>
        {children}
      </TestWrapper>
    ),
  });
};

describe('useSearch', () => {
  const mockFetchSearchResults = vi.mocked(fetchSearchResults);

  beforeEach(() => {
    vi.clearAllMocks();
    consoleSpy.log.mockClear();
    consoleSpy.error.mockClear();

    // Mock successful API response
    mockFetchSearchResults.mockResolvedValue({
      data: [
        {
          id: 'mit-001145244',
          type: 'document',
          attributes: {
            dct_title_s: 'Nondigitized paper map with library catalog link',
            dct_description_sm: ['A historical paper map from MIT collections'],
            dct_temporal_sm: ['1950'],
            dc_publisher_sm: ['MIT Libraries'],
            gbl_resourceClass_sm: ['Paper Maps'],
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
      ],
      meta: {
        totalCount: 1,
        page: 1,
        perPage: 10,
      },
      included: [],
    });
  });

  afterEach(() => {
    // Reset URL
    window.history.pushState({}, '', '/');
  });

  describe('Hook Initialization', () => {
    it('initializes with default values when no search params', async () => {
      const { result } = renderUseSearch();

      expect(result.current.query).toBe('');
      expect(result.current.page).toBe(1);
      expect(result.current.facets).toEqual([]);
      expect(result.current.sort).toBe('relevance');
      expect(result.current.isLoading).toBe(false);
      expect(result.current.error).toBeNull();
      expect(result.current.results).toBeNull();
      expect(mockFetchSearchResults).not.toHaveBeenCalled();
    });

    it('parses search parameters correctly', () => {
      const { result } = renderUseSearch(
        'q=geospatial%20data&page=2&sort=date'
      );

      expect(result.current.query).toBe('geospatial data');
      expect(result.current.page).toBe(2);
      expect(result.current.sort).toBe('date');
    });

    it('parses facet parameters correctly', () => {
      const { result } = renderUseSearch(
        'q=test&fq[dc_publisher_sm][]=MIT%20Libraries&fq[gbl_resourceClass_sm][]=Dataset'
      );

      expect(result.current.query).toBe('test');
      expect(result.current.facets).toEqual([
        { field: 'dc_publisher_sm', value: 'MIT Libraries' },
        { field: 'gbl_resourceClass_sm', value: 'Dataset' },
      ]);
    });

    it('handles multiple facets for same field', () => {
      const { result } = renderUseSearch(
        'q=test&fq[dc_publisher_sm][]=MIT%20Libraries&fq[dc_publisher_sm][]=Harvard%20University'
      );

      expect(result.current.facets).toEqual([
        { field: 'dc_publisher_sm', value: 'MIT Libraries' },
        { field: 'dc_publisher_sm', value: 'Harvard University' },
      ]);
    });

    it('logs debug information during initialization', () => {
      renderUseSearch('q=test&page=2');

      expect(consoleSpy.log).toHaveBeenCalledWith(
        '🔍 useSearch useEffect triggered with:',
        {
          query: 'test',
          page: 2,
          facetsLength: 0,
          excludeLength: 0,
          sort: 'relevance',
          advancedClauses: 0,
          setLastApiUrl: 'function',
        }
      );
    });
  });

  describe('Search API Calls', () => {
    it('performs search when query is provided', async () => {
      const { result } = renderUseSearch('q=geospatial%20data');

      await waitFor(() => {
        expect(mockFetchSearchResults).toHaveBeenCalledWith(
          'geospatial data',
          1,
          10,
          [],
          expect.any(Function),
          'relevance',
          [],
          []
        );
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.results).toBeDefined();
      expect(result.current.totalResults).toBe(1);
    });

    it('performs search when facets are provided without query', async () => {
      const { result } = renderUseSearch(
        'fq[dc_publisher_sm][]=MIT%20Libraries'
      );

      await waitFor(() => {
        expect(mockFetchSearchResults).toHaveBeenCalledWith(
          '',
          1,
          10,
          [{ field: 'dc_publisher_sm', value: 'MIT Libraries' }],
          expect.any(Function),
          'relevance',
          [],
          []
        );
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.results).toBeDefined();
    });

    it('skips search when no query, facets, or advanced clauses are provided', async () => {
      const { result } = renderUseSearch('');

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.results).toBeNull();
      expect(mockFetchSearchResults).not.toHaveBeenCalled();
    });

    it('handles search with custom sort parameter', async () => {
      const { result } = renderUseSearch('q=test&sort=date');

      await waitFor(() => {
        expect(mockFetchSearchResults).toHaveBeenCalledWith(
          'test',
          1,
          10,
          [],
          expect.any(Function),
          'date',
          [],
          []
        );
      });

      expect(result.current.sort).toBe('date');
    });

    it('handles search with custom page parameter', async () => {
      const { result } = renderUseSearch('q=test&page=3');

      await waitFor(() => {
        expect(mockFetchSearchResults).toHaveBeenCalledWith(
          'test',
          3,
          10,
          [],
          expect.any(Function),
          'relevance',
          [],
          []
        );
      });

      expect(result.current.page).toBe(3);
    });

    it('performs search when advanced clauses are provided', async () => {
      const advanced = encodeURIComponent(
        JSON.stringify([{ op: 'AND', f: 'dct_title_s', q: 'Iowa' }])
      );
      const { result } = renderUseSearch(`adv_q=${advanced}`);

      await waitFor(() => {
        expect(mockFetchSearchResults).toHaveBeenCalledWith(
          '',
          1,
          10,
          [],
          expect.any(Function),
          'relevance',
          [],
          [{ op: 'AND', field: 'dct_title_s', q: 'Iowa' }]
        );
      });

      expect(result.current.advancedQuery).toEqual([
        { op: 'AND', field: 'dct_title_s', q: 'Iowa' },
      ]);
    });

    it('logs search completion time', async () => {
      renderUseSearch('q=test');

      await waitFor(() => {
        expect(consoleSpy.log).toHaveBeenCalledWith(
          expect.stringMatching(/✅ Search completed in \d+\.\d+ms/)
        );
      });
    });

    it('logs results count', async () => {
      renderUseSearch('q=test');

      await waitFor(() => {
        expect(consoleSpy.log).toHaveBeenCalledWith('📊 Results: 1 items');
      });
    });
  });

  describe('Error Handling', () => {
    it('handles API errors gracefully', async () => {
      const errorMessage = 'Network error';
      mockFetchSearchResults.mockRejectedValue(new Error(errorMessage));

      const { result } = renderUseSearch('q=test');

      await waitFor(() => {
        expect(result.current.error).toBe(errorMessage);
        expect(result.current.isLoading).toBe(false);
        expect(result.current.results).toBeNull();
      });

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringMatching(/❌ Search failed after \d+\.\d+ms:/),
        expect.any(Error)
      );
    });

    it('handles non-Error exceptions', async () => {
      mockFetchSearchResults.mockRejectedValue('String error');

      const { result } = renderUseSearch('q=test');

      await waitFor(() => {
        expect(result.current.error).toBe('An error occurred');
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('resets error state on successful search', async () => {
      // First, trigger an error
      mockFetchSearchResults.mockRejectedValueOnce(new Error('First error'));
      const { result } = renderUseSearch('q=test');

      await waitFor(() => {
        expect(result.current.error).toBe('First error');
      });

      // Then, trigger a successful search by updating the query
      mockFetchSearchResults.mockResolvedValueOnce({
        data: [],
        meta: { totalCount: 0, page: 1, perPage: 10 },
        included: [],
      });

      act(() => {
        result.current.updateSearch({ query: 'new query' });
      });

      await waitFor(() => {
        expect(result.current.error).toBeNull();
        expect(result.current.results).toBeDefined();
      });
    });
  });

  describe('updateSearch Function', () => {
    it('updates query parameter', async () => {
      const { result } = renderUseSearch('q=old%20query');

      act(() => {
        result.current.updateSearch({ query: 'new query' });
      });

      expect(result.current.query).toBe('new query');
      expect(result.current.page).toBe(1); // Should reset page when query changes
    });

    it('removes query parameter when set to empty string', async () => {
      const { result } = renderUseSearch('q=test');

      act(() => {
        result.current.updateSearch({ query: '' });
      });

      expect(result.current.query).toBe('');
    });

    it('updates page parameter', async () => {
      const { result } = renderUseSearch('q=test&page=1');

      act(() => {
        result.current.updateSearch({ page: 3 });
      });

      expect(result.current.page).toBe(3);
    });

    it('removes page parameter when set to 1', async () => {
      const { result } = renderUseSearch('q=test&page=3');

      act(() => {
        result.current.updateSearch({ page: 1 });
      });

      expect(result.current.page).toBe(1);
    });

    it('updates sort parameter', async () => {
      const { result } = renderUseSearch('q=test');

      act(() => {
        result.current.updateSearch({ sort: 'date' });
      });

      expect(result.current.sort).toBe('date');
    });

    it('removes sort parameter when set to relevance', async () => {
      const { result } = renderUseSearch('q=test&sort=date');

      act(() => {
        result.current.updateSearch({ sort: 'relevance' });
      });

      expect(result.current.sort).toBe('relevance');
    });

    it('updates facets parameter', async () => {
      const { result } = renderUseSearch('q=test');

      const newFacets = [
        { field: 'dc_publisher_sm', value: 'MIT Libraries' },
        { field: 'gbl_resourceClass_sm', value: 'Dataset' },
      ];

      act(() => {
        result.current.updateSearch({ facets: newFacets });
      });

      expect(result.current.facets).toEqual(newFacets);
    });

    it('clears existing facets when updating', async () => {
      const { result } = renderUseSearch(
        'q=test&fq[dc_publisher_sm][]=Old%20Publisher'
      );

      const newFacets = [{ field: 'gbl_resourceClass_sm', value: 'Dataset' }];

      act(() => {
        result.current.updateSearch({ facets: newFacets });
      });

      expect(result.current.facets).toEqual(newFacets);
      expect(result.current.facets).not.toContainEqual({
        field: 'dc_publisher_sm',
        value: 'Old Publisher',
      });
    });

    it('preserves geo bbox params when updating facets', async () => {
      const geoAndFacetParams =
        'q=&include_filters[geo][type]=bbox&include_filters[geo][field]=dcat_bbox' +
        '&include_filters[geo][top_left][lat]=41.28&include_filters[geo][top_left][lon]=-90.76' +
        '&include_filters[geo][bottom_right][lat]=34.59&include_filters[geo][bottom_right][lon]=-82.28' +
        '&include_filters[gbl_resourceClass_sm][]=Maps';

      const { result } = renderUseSearch(geoAndFacetParams);

      act(() => {
        result.current.updateSearch({ facets: [] });
      });

      const params = new URLSearchParams(window.location.search);
      expect(params.get('include_filters[geo][type]')).toBe('bbox');
      expect(params.get('include_filters[geo][top_left][lat]')).toBe('41.28');
      expect(params.get('include_filters[geo][bottom_right][lat]')).toBe(
        '34.59'
      );
      expect(params.get('include_filters[gbl_resourceClass_sm][]')).toBeNull();
    });

    it('preserves year_range params when updating facets', async () => {
      const params =
        'q=&include_filters[year_range][start]=1910&include_filters[year_range][end]=1932' +
        '&include_filters[gbl_resourceClass_sm][]=Maps';

      const { result } = renderUseSearch(params);

      act(() => {
        result.current.updateSearch({ facets: [] });
      });

      const urlParams = new URLSearchParams(window.location.search);
      expect(urlParams.get('include_filters[year_range][start]')).toBe('1910');
      expect(urlParams.get('include_filters[year_range][end]')).toBe('1932');
      expect(
        urlParams.get('include_filters[gbl_resourceClass_sm][]')
      ).toBeNull();
    });

    it('updates advanced query parameter', async () => {
      const { result } = renderUseSearch('q=test');

      const advancedClauses = [{ op: 'AND', field: 'dct_title_s', q: 'Iowa' }];

      act(() => {
        result.current.updateSearch({ advancedQuery: advancedClauses });
      });

      await waitFor(() => {
        expect(mockFetchSearchResults).toHaveBeenLastCalledWith(
          'test',
          1,
          10,
          [],
          expect.any(Function),
          'relevance',
          [],
          advancedClauses
        );
      });

      expect(result.current.advancedQuery).toEqual(advancedClauses);
    });

    it('removes advanced query parameter when empty array is provided', async () => {
      const advanced = encodeURIComponent(
        JSON.stringify([{ op: 'AND', f: 'dct_title_s', q: 'Iowa' }])
      );
      const { result } = renderUseSearch(`q=test&adv_q=${advanced}`);

      expect(result.current.advancedQuery).toHaveLength(1);

      act(() => {
        result.current.updateSearch({ advancedQuery: [] });
      });

      await waitFor(() => {
        expect(result.current.advancedQuery).toEqual([]);
      });
    });

    it('handles multiple updates in sequence', async () => {
      const { result } = renderUseSearch('q=test');

      act(() => {
        result.current.updateSearch({ query: 'new query' });
      });

      act(() => {
        result.current.updateSearch({ page: 2 });
      });

      act(() => {
        result.current.updateSearch({ sort: 'date' });
      });

      expect(result.current.query).toBe('new query');
      expect(result.current.page).toBe(2);
      expect(result.current.sort).toBe('date');
    });

    it('handles partial updates', async () => {
      const { result } = renderUseSearch('q=test&page=2&sort=date');

      act(() => {
        result.current.updateSearch({ page: 3 });
      });

      expect(result.current.query).toBe('test'); // Should remain unchanged
      expect(result.current.page).toBe(3);
      expect(result.current.sort).toBe('date'); // Should remain unchanged
    });
  });

  describe('Return Values', () => {
    it('returns correct perPage value from results', async () => {
      mockFetchSearchResults.mockResolvedValueOnce({
        data: [],
        meta: { totalCount: 0, page: 1, perPage: 25 },
        included: [],
      });

      const { result } = renderUseSearch('q=test');

      await waitFor(() => {
        expect(result.current.perPage).toBe(25);
      });
    });

    it('returns default perPage when no results', () => {
      const { result } = renderUseSearch('');

      expect(result.current.perPage).toBe(10);
    });

    it('returns correct totalResults from results', async () => {
      mockFetchSearchResults.mockResolvedValueOnce({
        data: [],
        meta: { totalCount: 42, page: 1, perPage: 10 },
        included: [],
      });

      const { result } = renderUseSearch('q=test');

      await waitFor(() => {
        expect(result.current.totalResults).toBe(42);
      });
    });

    it('returns default totalResults when no results', () => {
      const { result } = renderUseSearch('');

      expect(result.current.totalResults).toBe(0);
    });

    it('returns facets array even when empty', () => {
      const { result } = renderUseSearch('');

      expect(result.current.facets).toEqual([]);
    });
  });

  describe('Edge Cases', () => {
    it('handles undefined query gracefully', async () => {
      const { result } = renderUseSearch('');

      expect(result.current.query).toBe('');
      expect(result.current.results).toBeNull();
    });

    it('handles invalid page numbers', async () => {
      const { result } = renderUseSearch('q=test&page=invalid');

      // Should default to page 1
      expect(result.current.page).toBe(1);
    });

    it('handles special characters in query', async () => {
      renderUseSearch(
        'q=geographic%20information%20systems%20%26%20remote%20sensing'
      );

      await waitFor(() => {
        expect(mockFetchSearchResults).toHaveBeenCalledWith(
          'geographic information systems & remote sensing',
          1,
          10,
          [],
          expect.any(Function),
          'relevance',
          [],
          []
        );
      });
    });

    it('handles complex facet combinations', async () => {
      renderUseSearch(
        'q=test&fq[dc_publisher_sm][]=MIT%20Libraries&fq[dc_publisher_sm][]=Harvard%20University&fq[gbl_resourceClass_sm][]=Dataset&fq[dct_temporal_sm][]=2020'
      );

      await waitFor(() => {
        expect(mockFetchSearchResults).toHaveBeenCalledWith(
          'test',
          1,
          10,
          [
            { field: 'dc_publisher_sm', value: 'MIT Libraries' },
            { field: 'dc_publisher_sm', value: 'Harvard University' },
            { field: 'gbl_resourceClass_sm', value: 'Dataset' },
            { field: 'dct_temporal_sm', value: '2020' },
          ],
          expect.any(Function),
          'relevance',
          [],
          []
        );
      });
    });

    it('handles empty facets array', async () => {
      const { result } = renderUseSearch('q=test');

      act(() => {
        result.current.updateSearch({ facets: [] });
      });

      expect(result.current.facets).toEqual([]);
    });

    it('handles very long queries', async () => {
      const longQuery =
        'This is a very long search query with many words that should be properly handled by the search hook';
      renderUseSearch(`q=${encodeURIComponent(longQuery)}`);

      await waitFor(() => {
        expect(mockFetchSearchResults).toHaveBeenCalledWith(
          longQuery,
          1,
          10,
          [],
          expect.any(Function),
          'relevance',
          [],
          []
        );
      });
    });
  });

  describe('Performance and Timing', () => {
    it('measures search performance', async () => {
      renderUseSearch('q=test');

      await waitFor(() => {
        expect(consoleSpy.log).toHaveBeenCalledWith(
          expect.stringMatching(/✅ Search completed in \d+\.\d+ms/)
        );
      });
    });

    it('handles rapid successive updates', async () => {
      const { result } = renderUseSearch('q=test');

      act(() => {
        result.current.updateSearch({ query: 'query1' });
        result.current.updateSearch({ query: 'query2' });
        result.current.updateSearch({ query: 'query3' });
      });

      expect(result.current.query).toBe('query3');
    });
  });

  describe('Integration with Real Data', () => {
    it('works with real fixture data patterns', async () => {
      const { result } = renderUseSearch(
        'q=geospatial%20data&fq[dc_publisher_sm][]=MIT%20Libraries&fq[gbl_resourceClass_sm][]=Dataset&sort=date&page=2'
      );

      await waitFor(() => {
        expect(mockFetchSearchResults).toHaveBeenCalledWith(
          'geospatial data',
          2,
          10,
          [
            { field: 'dc_publisher_sm', value: 'MIT Libraries' },
            { field: 'gbl_resourceClass_sm', value: 'Dataset' },
          ],
          expect.any(Function),
          'date',
          [],
          []
        );
      });

      expect(result.current.query).toBe('geospatial data');
      expect(result.current.page).toBe(2);
      expect(result.current.sort).toBe('date');
      expect(result.current.facets).toEqual([
        { field: 'dc_publisher_sm', value: 'MIT Libraries' },
        { field: 'gbl_resourceClass_sm', value: 'Dataset' },
      ]);
    });

    it('handles real-world search scenarios', async () => {
      const testCases = [
        {
          params: 'q=maps',
          expectedQuery: 'maps',
          expectedFacets: [],
        },
        {
          params: 'q=geospatial%20data&fq[dc_publisher_sm][]=MIT%20Libraries',
          expectedQuery: 'geospatial data',
          expectedFacets: [
            { field: 'dc_publisher_sm', value: 'MIT Libraries' },
          ],
        },
        {
          params:
            'fq[gbl_resourceClass_sm][]=Dataset&fq[dct_temporal_sm][]=2020',
          expectedQuery: '',
          expectedFacets: [
            { field: 'gbl_resourceClass_sm', value: 'Dataset' },
            { field: 'dct_temporal_sm', value: '2020' },
          ],
        },
      ];

      for (const testCase of testCases) {
        const { result } = renderUseSearch(testCase.params);

        expect(result.current.query).toBe(testCase.expectedQuery);
        expect(result.current.facets).toEqual(testCase.expectedFacets);

        await waitFor(() => {
          expect(mockFetchSearchResults).toHaveBeenCalled();
        });

        vi.clearAllMocks();
      }
    });
  });
});

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchBookmarkedResources,
  fetchFacetValues,
  fetchSearchResults,
} from '../../services/api';
import type { FacetValuesResponse } from '../../types/api';

// Mock fetch
global.fetch = vi.fn();

// Unmock the API service to test the real implementation
vi.unmock('../../services/api');

describe('fetchBookmarkedResources', () => {
  it('constructs bookmark URL without trailing slash redirect', async () => {
    const ids = ['123', '456'];
    const onApiCall = vi.fn();

    // Mock success response
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ data: [] }),
    });

    await fetchBookmarkedResources(ids, onApiCall);

    expect(onApiCall).toHaveBeenCalled();
    const url = new URL(onApiCall.mock.calls[0][0]);
    const includeIds = url.searchParams.getAll('include_filters[id][]');

    // Path must end in /search (not /search/) to avoid redirect behavior.
    expect(url.pathname.endsWith('/search')).toBe(true);
    expect(url.pathname.endsWith('/search/')).toBe(false);
    expect(includeIds).toEqual(ids);
    expect(url.searchParams.get('format')).toBe('json');
    expect(url.searchParams.get('search_field')).toBe('all_fields');
    expect(url.searchParams.get('q')).toBe('');
  });
});

describe('fetchFacetValues', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Ensure we're in browser environment
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://example.com',
      },
      writable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  const mockFacetResponse: FacetValuesResponse = {
    data: [
      {
        type: 'facet_value',
        id: 'Minnesota',
        attributes: {
          value: 'Minnesota',
          label: 'Minnesota',
          hits: 100,
        },
      },
      {
        type: 'facet_value',
        id: 'Wisconsin',
        attributes: {
          value: 'Wisconsin',
          label: 'Wisconsin',
          hits: 50,
        },
      },
    ],
    meta: {
      totalCount: 2,
      totalPages: 1,
      currentPage: 1,
      perPage: 10,
      facetName: 'dct_spatial_sm',
      sort: 'count_desc',
    },
  };

  it('constructs correct proxy URL with facetName in path (browser)', async () => {
    const searchParams = new URLSearchParams();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFacetResponse,
    });
    global.fetch = mockFetch;

    const result = await fetchFacetValues({
      facetName: 'dct_spatial_sm',
      searchParams,
      page: 1,
      perPage: 10,
      sort: 'count_desc',
    });

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const callUrl = mockFetch.mock.calls[0][0];
    const url = new URL(callUrl);

    // Verify path includes facetName (route is /search/facets/:facetName to go through SSR)
    expect(url.pathname).toBe('/search/facets/dct_spatial_sm');
    expect(url.searchParams.get('page')).toBe('1');
    expect(url.searchParams.get('per_page')).toBe('10');
    expect(url.searchParams.get('sort')).toBe('count_desc');
    expect(result).toEqual(mockFacetResponse);
  });

  it('forwards search query parameter (q)', async () => {
    const searchParams = new URLSearchParams('q=lakes');
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFacetResponse,
    });
    global.fetch = mockFetch;

    await fetchFacetValues({
      facetName: 'dct_spatial_sm',
      searchParams,
    });

    const callUrl = mockFetch.mock.calls[0][0];
    const url = new URL(callUrl);
    expect(url.searchParams.get('q')).toBe('lakes');
  });

  it('forwards advanced query parameter (adv_q)', async () => {
    const advQuery = JSON.stringify([
      { op: 'AND', f: 'dct_title_s', q: 'Iowa' },
    ]);
    const searchParams = new URLSearchParams(`adv_q=${advQuery}`);
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFacetResponse,
    });
    global.fetch = mockFetch;

    await fetchFacetValues({
      facetName: 'dct_spatial_sm',
      searchParams,
    });

    const callUrl = mockFetch.mock.calls[0][0];
    const url = new URL(callUrl);
    expect(url.searchParams.get('adv_q')).toBe(advQuery);
  });

  it('forwards include_filters parameters', async () => {
    const searchParams = new URLSearchParams();
    searchParams.append('include_filters[dct_spatial_sm][]', 'Minnesota');
    searchParams.append('include_filters[dct_spatial_sm][]', 'Wisconsin');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFacetResponse,
    });
    global.fetch = mockFetch;

    await fetchFacetValues({
      facetName: 'dct_spatial_sm',
      searchParams,
    });

    const callUrl = mockFetch.mock.calls[0][0];
    const url = new URL(callUrl);
    const values = url.searchParams.getAll('include_filters[dct_spatial_sm][]');
    expect(values).toContain('Minnesota');
    expect(values).toContain('Wisconsin');
  });

  it('forwards exclude_filters parameters', async () => {
    const searchParams = new URLSearchParams();
    searchParams.append('exclude_filters[dct_spatial_sm][]', 'Illinois');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFacetResponse,
    });
    global.fetch = mockFetch;

    await fetchFacetValues({
      facetName: 'dct_spatial_sm',
      searchParams,
    });

    const callUrl = mockFetch.mock.calls[0][0];
    const url = new URL(callUrl);
    expect(url.searchParams.get('exclude_filters[dct_spatial_sm][]')).toBe(
      'Illinois'
    );
  });

  it('forwards fq (legacy filter) parameters', async () => {
    const searchParams = new URLSearchParams();
    searchParams.append('fq[gbl_resourceClass_sm][]', 'Maps');

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFacetResponse,
    });
    global.fetch = mockFetch;

    await fetchFacetValues({
      facetName: 'dct_spatial_sm',
      searchParams,
    });

    const callUrl = mockFetch.mock.calls[0][0];
    const url = new URL(callUrl);
    expect(url.searchParams.get('fq[gbl_resourceClass_sm][]')).toBe('Maps');
  });

  it('sets q_facet parameter when provided', async () => {
    const searchParams = new URLSearchParams();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFacetResponse,
    });
    global.fetch = mockFetch;

    await fetchFacetValues({
      facetName: 'dct_spatial_sm',
      searchParams,
      qFacet: 'Minnesota',
    });

    const callUrl = mockFetch.mock.calls[0][0];
    const url = new URL(callUrl);
    expect(url.searchParams.get('q_facet')).toBe('Minnesota');
  });

  it('normalizes page to minimum 1', async () => {
    const searchParams = new URLSearchParams();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFacetResponse,
    });
    global.fetch = mockFetch;

    await fetchFacetValues({
      facetName: 'dct_spatial_sm',
      searchParams,
      page: 0,
    });

    const callUrl = mockFetch.mock.calls[0][0];
    const url = new URL(callUrl);
    expect(url.searchParams.get('page')).toBe('1');
  });

  it('normalizes perPage to between 1 and 100', async () => {
    const searchParams = new URLSearchParams();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockFacetResponse,
    });
    global.fetch = mockFetch;

    // Test minimum
    await fetchFacetValues({
      facetName: 'dct_spatial_sm',
      searchParams,
      perPage: 0,
    });
    let callUrl = mockFetch.mock.calls[0][0];
    let url = new URL(callUrl);
    expect(url.searchParams.get('per_page')).toBe('1');

    // Test maximum
    mockFetch.mockClear();
    await fetchFacetValues({
      facetName: 'dct_spatial_sm',
      searchParams,
      perPage: 200,
    });
    callUrl = mockFetch.mock.calls[0][0];
    url = new URL(callUrl);
    expect(url.searchParams.get('per_page')).toBe('100');
  });

  it('handles error responses', async () => {
    const searchParams = new URLSearchParams();
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      statusText: 'Not Found',
      text: async () => '{"detail":"Not Found"}',
    });
    global.fetch = mockFetch;

    await expect(
      fetchFacetValues({
        facetName: 'dct_spatial_sm',
        searchParams,
      })
    ).rejects.toThrow('Failed to fetch facet values: Not Found');
  });

  it('handles all sort options', async () => {
    const searchParams = new URLSearchParams();
    const sortOptions: Array<
      'count_desc' | 'count_asc' | 'alpha_asc' | 'alpha_desc'
    > = ['count_desc', 'count_asc', 'alpha_asc', 'alpha_desc'];

    for (const sort of sortOptions) {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockFacetResponse,
      });
      global.fetch = mockFetch;

      await fetchFacetValues({
        facetName: 'dct_spatial_sm',
        searchParams,
        sort,
      });

      const callUrl = mockFetch.mock.calls[0][0];
      const url = new URL(callUrl);
      expect(url.searchParams.get('sort')).toBe(sort);
    }
  });
});

describe('fetchSearchResults', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('forwards bbox relation when present in URL params', async () => {
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://example.com',
        href: 'https://example.com/search?include_filters[geo][type]=bbox&include_filters[geo][field]=dcat_bbox&include_filters[geo][top_left][lat]=45&include_filters[geo][top_left][lon]=-109&include_filters[geo][bottom_right][lat]=41&include_filters[geo][bottom_right][lon]=-104&include_filters[geo][relation]=within',
      },
      writable: true,
    });

    const onApiCall = vi.fn();
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ data: [], meta: {}, included: [] }),
    });

    await fetchSearchResults('maps', 1, 10, [], onApiCall);

    expect(onApiCall).toHaveBeenCalledTimes(1);
    const requestUrl = new URL(onApiCall.mock.calls[0][0]);
    expect(requestUrl.searchParams.get('include_filters[geo][relation]')).toBe(
      'within'
    );
  });

  it('does not add bbox relation when relation is absent', async () => {
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://example.com',
        href: 'https://example.com/search?include_filters[geo][type]=bbox&include_filters[geo][field]=dcat_bbox&include_filters[geo][top_left][lat]=45&include_filters[geo][top_left][lon]=-109&include_filters[geo][bottom_right][lat]=41&include_filters[geo][bottom_right][lon]=-104',
      },
      writable: true,
    });

    const onApiCall = vi.fn();
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ data: [], meta: {}, included: [] }),
    });

    await fetchSearchResults('maps', 1, 10, [], onApiCall);

    const requestUrl = new URL(onApiCall.mock.calls[0][0]);
    expect(requestUrl.searchParams.get('include_filters[geo][relation]')).toBeNull();
  });
});

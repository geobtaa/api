import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchBookmarkedResources,
  fetchFeaturedResourcePreview,
  fetchFacetValues,
  fetchHomeBlogPosts,
  fetchMapH3,
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

describe('fetchMapH3', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://example.com',
        hostname: 'example.com',
      },
      writable: true,
    });
  });

  it('adds a cache-busting version while preserving advanced search params', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        resolution: 2,
        hexes: [['822aa7fffffffff', 99]],
        globalCount: 3,
      }),
    });
    global.fetch = mockFetch;

    const advQuery = JSON.stringify([
      { op: 'AND', f: 'dct_title_s', q: 'water' },
      { op: 'AND', f: 'dct_spatial_sm', q: 'Pennsylvania' },
    ]);

    await fetchMapH3('', undefined, 2, `adv_q=${encodeURIComponent(advQuery)}`);

    const callUrl = mockFetch.mock.calls[0][0];
    const url = new URL(callUrl);
    expect(url.pathname).toBe('/map/h3');
    expect(url.searchParams.get('_v')).toBe('2');
    expect(url.searchParams.get('adv_q')).toBe(advQuery);
  });
});

describe('fetchFeaturedResourcePreview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://example.com',
        hostname: 'example.com',
      },
      writable: true,
    });
  });

  it('requests the lightweight homepage profile for featured previews', async () => {
    const onApiCall = vi.fn();

    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        data: {
          id: 'resource-1',
          type: 'resource',
          attributes: { ogm: { id: 'resource-1', dct_title_s: 'Resource 1' } },
        },
      }),
    });

    await fetchFeaturedResourcePreview('resource-1', onApiCall);

    expect(onApiCall).toHaveBeenCalledTimes(1);
    const url = new URL(onApiCall.mock.calls[0][0]);
    expect(url.pathname).toBe('/api-proxy/resources/resource-1');
    expect(url.searchParams.get('format')).toBe('json');
    expect(url.searchParams.get('ui_profile')).toBe('homepage');
  });
});

describe('fetchHomeBlogPosts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('prefers the same-origin API route before the SSR proxy on deployed hosts', async () => {
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://example.com',
        hostname: 'example.com',
      },
      writable: true,
    });

    (global.fetch as any).mockResolvedValue({
      ok: true,
      headers: { get: () => 'application/json' },
      text: async () => JSON.stringify({ data: [], meta: {} }),
    });

    await fetchHomeBlogPosts({ limit: 3, theme: 'btaa' });

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const url = new URL((global.fetch as any).mock.calls[0][0]);
    expect(url.pathname).toBe('/api/v1/home/blog-posts');
    expect(url.searchParams.get('limit')).toBe('3');
    expect(url.searchParams.get('theme')).toBe('btaa');
  });

  it('falls back to the SSR proxy when the same-origin API path is not available', async () => {
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'http://localhost:3000',
        hostname: 'localhost',
      },
      writable: true,
    });

    (global.fetch as any)
      .mockResolvedValueOnce({
        ok: true,
        headers: { get: () => 'text/html' },
        text: async () => '<!doctype html><html></html>',
      })
      .mockResolvedValueOnce({
        ok: true,
        headers: { get: () => 'application/json' },
        text: async () =>
          JSON.stringify({ data: [{ slug: 'latest-post' }], meta: {} }),
      });

    const response = await fetchHomeBlogPosts({ limit: 3, theme: 'btaa' });

    expect((global.fetch as any).mock.calls).toHaveLength(2);
    const firstUrl = new URL((global.fetch as any).mock.calls[0][0]);
    const secondUrl = new URL((global.fetch as any).mock.calls[1][0]);
    expect(firstUrl.pathname).toBe('/api/v1/home/blog-posts');
    expect(secondUrl.pathname).toBe('/home/blog-posts');
    expect(response.data).toEqual([{ slug: 'latest-post' }]);
  });
});

describe('fetchSearchResults', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('uses the keyed frontend search-results proxy in the browser', async () => {
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://example.com',
        href: 'https://example.com/search?q=maps',
      },
      writable: true,
    });

    const onApiCall = vi.fn();
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ data: [], meta: {}, included: [] }),
    });

    await fetchSearchResults('maps', 1, 10, [], onApiCall);

    const fetchUrl = new URL((global.fetch as any).mock.calls[0][0]);
    expect(fetchUrl.pathname).toBe('/search/results');
    expect(fetchUrl.searchParams.get('q')).toBe('maps');

    const displayedApiUrl = new URL(onApiCall.mock.calls[0][0]);
    expect(displayedApiUrl.pathname).toBe('/api/v1/search');
  });

  it('replays source search params when paginating from a resource page', async () => {
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://example.com',
        href: 'https://example.com/resources/abc123',
      },
      writable: true,
    });

    const onApiCall = vi.fn();
    const sourceSearchParams = new URLSearchParams();
    const advQuery = JSON.stringify([
      { op: 'AND', f: 'dct_title_s', q: 'Chicago' },
    ]);

    sourceSearchParams.set('q', 'chicago');
    sourceSearchParams.set('sort', 'year_desc');
    sourceSearchParams.set('adv_q', advQuery);
    sourceSearchParams.append(
      'include_filters[gbl_resourceClass_sm][]',
      'Maps'
    );
    sourceSearchParams.append(
      'exclude_filters[dct_accessRights_s][]',
      'Restricted'
    );
    sourceSearchParams.set('include_filters[year_range][start]', '1900');
    sourceSearchParams.set('include_filters[year_range][end]', '1950');
    sourceSearchParams.set('include_filters[geo][type]', 'bbox');
    sourceSearchParams.set('include_filters[geo][field]', 'dcat_bbox');
    sourceSearchParams.set('include_filters[geo][top_left][lat]', '45');
    sourceSearchParams.set('include_filters[geo][top_left][lon]', '-109');
    sourceSearchParams.set('include_filters[geo][bottom_right][lat]', '41');
    sourceSearchParams.set('include_filters[geo][bottom_right][lon]', '-104');
    sourceSearchParams.set('include_filters[geo][relation]', 'within');

    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({ data: [], meta: {}, included: [] }),
    });

    await fetchSearchResults(
      '',
      2,
      10,
      [],
      onApiCall,
      undefined,
      [],
      [],
      undefined,
      sourceSearchParams
    );

    expect(onApiCall).toHaveBeenCalledTimes(1);
    const requestUrl = new URL(onApiCall.mock.calls[0][0]);
    expect(requestUrl.searchParams.get('q')).toBe('chicago');
    expect(requestUrl.searchParams.get('page')).toBe('2');
    expect(requestUrl.searchParams.get('per_page')).toBe('10');
    expect(requestUrl.searchParams.get('sort')).toBe('year_desc');
    expect(requestUrl.searchParams.get('adv_q')).toBe(advQuery);
    expect(
      requestUrl.searchParams.getAll('include_filters[gbl_resourceClass_sm][]')
    ).toEqual(['Maps']);
    expect(
      requestUrl.searchParams.getAll('exclude_filters[dct_accessRights_s][]')
    ).toEqual(['Restricted']);
    expect(
      requestUrl.searchParams.get('include_filters[year_range][start]')
    ).toBe('1900');
    expect(
      requestUrl.searchParams.get('include_filters[year_range][end]')
    ).toBe('1950');
    expect(requestUrl.searchParams.get('include_filters[geo][relation]')).toBe(
      'within'
    );
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
    expect(
      requestUrl.searchParams.get('include_filters[geo][relation]')
    ).toBeNull();
  });
});

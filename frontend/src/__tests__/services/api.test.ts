import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  fetchBookmarkedResources,
  fetchFeaturedResourcePreview,
  fetchFacetValues,
  fetchHomeBlogPosts,
  fetchMapH3,
  fetchNominatimSearch,
  fetchSearchResults,
} from '../../services/api';
import { TURNSTILE_REQUIRED_EVENT } from '../../services/turnstile';
import { loader as placesSuggestLoader } from '../../../app/routes/places.suggest';
import type { FacetValuesResponse } from '../../types/api';

// Mock fetch
global.fetch = vi.fn();

// Unmock the API service to test the real implementation
vi.unmock('../../services/api');

describe('fetchNominatimSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://example.com',
      },
      writable: true,
    });
  });

  it('requests place suggestions through the same-origin server cache', async () => {
    const mockResponse = {
      jsonapi: { version: '1.1', profile: [] },
      links: { self: '' },
      meta: {
        totalCount: 1,
        totalPages: 1,
        currentPage: 1,
        perPage: 5,
        query: 'Milwaukee',
        offset: 0,
        gazetteer: 'nominatim',
      },
      data: [
        {
          id: 'nominatim-123',
          type: 'gazetteer_place',
          attributes: {
            id: 123,
            name: 'Milwaukee',
          },
        },
      ],
    };
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });
    global.fetch = mockFetch;

    const result = await fetchNominatimSearch(' Milwaukee ', 10);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const url = new URL(mockFetch.mock.calls[0][0]);
    expect(url.origin).toBe('https://example.com');
    expect(url.pathname).toBe('/places/suggest');
    expect(url.searchParams.get('q')).toBe('Milwaukee');
    expect(url.searchParams.get('limit')).toBe('5');
    expect(mockFetch.mock.calls[0][1]).toMatchObject({
      credentials: 'same-origin',
    });
    expect(result.data[0].attributes.name).toBe('Milwaukee');
  });
});

describe('placesSuggestLoader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('proxies place suggestions through the cached backend endpoint', async () => {
    const payload = {
      data: [
        {
          id: 'nominatim-123',
          type: 'gazetteer_place',
          attributes: {
            name: 'Milwaukee',
          },
        },
      ],
    };
    const body = new TextEncoder().encode(JSON.stringify(payload));
    const mockFetch = vi.fn().mockResolvedValue({
      status: 200,
      ok: true,
      headers: new Headers({
        'content-type': 'application/json; charset=utf-8',
        'cache-control': 'public, max-age=0, s-maxage=2592000',
        'content-encoding': 'gzip',
      }),
      arrayBuffer: async () => body.buffer,
    });
    global.fetch = mockFetch;

    const response = (await placesSuggestLoader({
      request: new Request(
        'http://localhost/places/suggest?q=Milwaukee&limit=10',
        {
          headers: { 'accept-language': 'en-US,en;q=0.9' },
        }
      ),
      params: {},
      context: {},
    })) as Response;

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const upstreamUrl = new URL(mockFetch.mock.calls[0][0]);
    const upstreamHeaders = new Headers(mockFetch.mock.calls[0][1]?.headers);
    expect(upstreamUrl.pathname).toBe('/api/v1/gazetteers/nominatim/search');
    expect(upstreamUrl.searchParams.get('q')).toBe('Milwaukee');
    expect(upstreamUrl.searchParams.get('limit')).toBe('5');
    expect(upstreamHeaders.get('accept-language')).toBe('en-US,en;q=0.9');

    expect(response.headers.get('content-encoding')).toBeNull();
    expect(response.headers.get('cache-control')).toBe(
      'public, max-age=0, s-maxage=2592000'
    );
    const json = await response.json();
    expect(json.data[0].attributes.name).toBe('Milwaukee');
  });
});

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
    vi.stubEnv('VITE_API_BASE_URL', 'https://example.com/api-proxy');
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://example.com',
        hostname: 'example.com',
      },
      writable: true,
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
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

  afterEach(() => {
    window.sessionStorage.clear();
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

  it('signals the Turnstile gate when the search session has expired', async () => {
    Object.defineProperty(window, 'location', {
      value: {
        origin: 'https://example.com',
        href: 'https://example.com/search?q=maps',
      },
      writable: true,
    });

    window.sessionStorage.setItem(
      'btaa_turnstile_session',
      'expired-session'
    );
    const turnstileRequired = vi.fn();
    window.addEventListener(TURNSTILE_REQUIRED_EVENT, turnstileRequired);

    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
      headers: new Headers({ 'X-Turnstile-Required': 'true' }),
      text: async () =>
        JSON.stringify({
          error: 'turnstile_required',
          message: 'A verified browser session is required for this request.',
        }),
    });
    global.fetch = mockFetch;

    try {
      await expect(fetchSearchResults('maps', 1, 10, [])).rejects.toMatchObject(
        {
          status: 403,
          code: 'turnstile_required',
          message: 'A verified browser session is required for this request.',
        }
      );

      expect(
        window.sessionStorage.getItem('btaa_turnstile_session')
      ).toBeNull();
      expect(turnstileRequired).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener(TURNSTILE_REQUIRED_EVENT, turnstileRequired);
    }
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
    expect(requestUrl.searchParams.get('per_page')).toBe('20');
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

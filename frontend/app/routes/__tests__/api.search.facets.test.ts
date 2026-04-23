import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loader } from '../api.search.facets';
import type { LoaderFunctionArgs } from 'react-router';
import type { FacetValuesResponse } from '../../../src/types/api';

// Mock serverFetch
vi.mock('../../lib/server-api', () => ({
  serverFetch: vi.fn(),
}));

import { serverFetch } from '../../lib/server-api';

describe('api.search.facets loader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
    ],
    meta: {
      totalCount: 1,
      totalPages: 1,
      currentPage: 1,
      perPage: 10,
      facetName: 'dct_spatial_sm',
      sort: 'count_desc',
    },
  };

  it('extracts facetName from path params', async () => {
    const mockRequest = new Request(
      'https://example.com/search/facets/dct_spatial_sm'
    );
    const mockParams = { facetName: 'dct_spatial_sm' };
    const loaderArgs = {
      params: mockParams,
      request: mockRequest,
    } as unknown as LoaderFunctionArgs;

    vi.mocked(serverFetch).mockResolvedValue(
      new Response(JSON.stringify(mockFacetResponse), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
        },
      })
    );

    const response = await loader(loaderArgs);
    const data = await response.json();

    expect(serverFetch).toHaveBeenCalledWith(
      expect.stringContaining('/search/facets/dct_spatial_sm')
    );
    expect(data).toEqual(mockFacetResponse);
  });

  it('returns 400 error when facetName is missing', async () => {
    const mockRequest = new Request('https://example.com/search/facets/');
    const mockParams = {};
    const loaderArgs = {
      params: mockParams,
      request: mockRequest,
    } as unknown as LoaderFunctionArgs;

    await expect(loader(loaderArgs)).rejects.toThrow();
  });

  it('forwards all query parameters to upstream API', async () => {
    const mockRequest = new Request(
      'https://example.com/search/facets/dct_spatial_sm?page=2&per_page=20&sort=alpha_asc&q=lakes&q_facet=Minnesota'
    );
    const mockParams = { facetName: 'dct_spatial_sm' };
    const loaderArgs = {
      params: mockParams,
      request: mockRequest,
    } as unknown as LoaderFunctionArgs;

    vi.mocked(serverFetch).mockResolvedValue(
      new Response(JSON.stringify(mockFacetResponse), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
        },
      })
    );

    await loader(loaderArgs);

    const callArg = vi.mocked(serverFetch).mock.calls[0][0];
    expect(callArg).toContain('/search/facets/dct_spatial_sm');
    expect(callArg).toContain('page=2');
    expect(callArg).toContain('per_page=20');
    expect(callArg).toContain('sort=alpha_asc');
    expect(callArg).toContain('q=lakes');
    expect(callArg).toContain('q_facet=Minnesota');
  });

  it('forwards include_filters parameters', async () => {
    // URLSearchParams encodes brackets, so we need to use encodeURIComponent
    const param1 = encodeURIComponent('include_filters[dct_spatial_sm][]');
    const mockRequest = new Request(
      `https://example.com/search/facets/dct_spatial_sm?${param1}=Minnesota&${param1}=Wisconsin`
    );
    const mockParams = { facetName: 'dct_spatial_sm' };
    const loaderArgs = {
      params: mockParams,
      request: mockRequest,
    } as unknown as LoaderFunctionArgs;

    vi.mocked(serverFetch).mockResolvedValue(
      new Response(JSON.stringify(mockFacetResponse), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
        },
      })
    );

    await loader(loaderArgs);

    const callArg = vi.mocked(serverFetch).mock.calls[0][0];
    // The URL will contain the encoded parameter (%5B = [, %5D = ])
    expect(callArg).toMatch(/include_filters%5Bdct_spatial_sm%5D%5B%5D/);
  });

  it('forwards exclude_filters parameters', async () => {
    const param = encodeURIComponent('exclude_filters[dct_spatial_sm][]');
    const mockRequest = new Request(
      `https://example.com/search/facets/dct_spatial_sm?${param}=Illinois`
    );
    const mockParams = { facetName: 'dct_spatial_sm' };
    const loaderArgs = {
      params: mockParams,
      request: mockRequest,
    } as unknown as LoaderFunctionArgs;

    vi.mocked(serverFetch).mockResolvedValue(
      new Response(JSON.stringify(mockFacetResponse), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
        },
      })
    );

    await loader(loaderArgs);

    const callArg = vi.mocked(serverFetch).mock.calls[0][0];
    // The URL will contain the encoded parameter (%5B = [, %5D = ])
    expect(callArg).toMatch(/exclude_filters%5Bdct_spatial_sm%5D%5B%5D/);
  });

  it('forwards adv_q parameter', async () => {
    const advQuery = encodeURIComponent(
      JSON.stringify([{ op: 'AND', f: 'dct_title_s', q: 'Iowa' }])
    );
    const mockRequest = new Request(
      `https://example.com/search/facets/dct_spatial_sm?adv_q=${advQuery}`
    );
    const mockParams = { facetName: 'dct_spatial_sm' };
    const loaderArgs = {
      params: mockParams,
      request: mockRequest,
    } as unknown as LoaderFunctionArgs;

    vi.mocked(serverFetch).mockResolvedValue(
      new Response(JSON.stringify(mockFacetResponse), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
        },
      })
    );

    await loader(loaderArgs);

    const callArg = vi.mocked(serverFetch).mock.calls[0][0];
    expect(callArg).toContain('adv_q=');
  });

  it('handles API errors and propagates status', async () => {
    const mockRequest = new Request(
      'https://example.com/search/facets/dct_spatial_sm'
    );
    const mockParams = { facetName: 'dct_spatial_sm' };
    const loaderArgs = {
      params: mockParams,
      request: mockRequest,
    } as unknown as LoaderFunctionArgs;

    vi.mocked(serverFetch).mockResolvedValue(
      new Response('API request failed: 404 Not Found', {
        status: 404,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
        },
      })
    );

    const response = await loader(loaderArgs);
    expect(response.status).toBe(404);
  });

  it('handles general errors and returns 500', async () => {
    const mockRequest = new Request(
      'https://example.com/search/facets/dct_spatial_sm'
    );
    const mockParams = { facetName: 'dct_spatial_sm' };
    const loaderArgs = {
      params: mockParams,
      request: mockRequest,
    } as unknown as LoaderFunctionArgs;

    vi.mocked(serverFetch).mockRejectedValue(new Error('Network error'));

    const response = await loader(loaderArgs);
    expect(response.status).toBe(500);
    const text = await response.text();
    expect(text).toBe('Failed to fetch facet values');
  });

  it('returns JSON response with correct content type', async () => {
    const mockRequest = new Request(
      'https://example.com/search/facets/dct_spatial_sm'
    );
    const mockParams = { facetName: 'dct_spatial_sm' };
    const loaderArgs = {
      params: mockParams,
      request: mockRequest,
    } as unknown as LoaderFunctionArgs;

    vi.mocked(serverFetch).mockResolvedValue(
      new Response(JSON.stringify(mockFacetResponse), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
        },
      })
    );

    const response = await loader(loaderArgs);
    expect(response.headers.get('content-type')).toContain('application/json');
    const data = await response.json();
    expect(data).toEqual(mockFacetResponse);
  });

  it('preserves upstream cache headers', async () => {
    const mockRequest = new Request(
      'https://example.com/search/facets/dct_spatial_sm'
    );
    const mockParams = { facetName: 'dct_spatial_sm' };
    const loaderArgs = {
      params: mockParams,
      request: mockRequest,
    } as unknown as LoaderFunctionArgs;

    vi.mocked(serverFetch).mockResolvedValue(
      new Response(JSON.stringify(mockFacetResponse), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Cache-Control':
            'public, max-age=0, s-maxage=43200, stale-while-revalidate=300',
          ETag: 'W/"facet-test"',
          Vary: 'Accept-Encoding, Accept',
          'X-Cache': 'HIT',
        },
      })
    );

    const response = await loader(loaderArgs);

    expect(response.headers.get('cache-control')).toContain('s-maxage=43200');
    expect(response.headers.get('etag')).toBe('W/"facet-test"');
    expect(response.headers.get('vary')).toBe('Accept-Encoding, Accept');
    expect(response.headers.get('x-cache')).toBe('HIT');
  });
});

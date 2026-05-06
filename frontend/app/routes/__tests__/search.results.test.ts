import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { LoaderFunctionArgs } from 'react-router';
import { loader } from '../search.results';
import { serverFetchWithTheme } from '../../lib/server-api';
import type { JsonApiResponse } from '../../../src/types/api';

vi.mock('../../lib/server-api', () => ({
  serverFetchWithTheme: vi.fn(),
}));

describe('search results proxy loader', () => {
  const mockSearchResponse: JsonApiResponse = {
    data: [],
    meta: {
      totalCount: 0,
      totalPages: 0,
      currentPage: 1,
      perPage: 10,
      query: 'maps',
    },
    included: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('forwards search params to upstream search with the request context', async () => {
    const request = new Request(
      'https://example.com/search/results?q=maps&page=2&per_page=10',
      {
        headers: {
          Accept: 'application/vnd.api+json, application/json',
          'X-BTAA-Client-Name': 'geoportal-web',
          'X-BTAA-Client-Channel': 'browser',
          'X-BTAA-Client-Version': 'test',
          'X-Visit-Token': 'visit-123',
        },
      }
    );

    vi.mocked(serverFetchWithTheme).mockResolvedValue(
      new Response(JSON.stringify(mockSearchResponse), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Server-Timing': 'total;dur=4.2, semantic_cache;desc="hit"',
          'X-Cache': 'HIT',
          'X-Search-Semantic-Cache': 'HIT',
        },
      })
    );

    const response = await loader({
      request,
      params: {},
    } as unknown as LoaderFunctionArgs);

    expect(serverFetchWithTheme).toHaveBeenCalledTimes(1);
    const [callRequest, pathAndQuery, options] =
      vi.mocked(serverFetchWithTheme).mock.calls[0];

    expect(callRequest).toBe(request);
    expect(pathAndQuery).toContain('/search?');
    expect(pathAndQuery).toContain('q=maps');
    expect(pathAndQuery).toContain('page=2');
    expect(pathAndQuery).toContain('per_page=10');
    expect((options?.headers as Headers).get('x-btaa-client-name')).toBe(
      'geoportal-web'
    );
    expect((options?.headers as Headers).get('x-visit-token')).toBe(
      'visit-123'
    );
    expect((options?.headers as Headers).get('x-btaa-turnstile-gate')).toBe(
      'frontend-search'
    );

    expect(response.headers.get('content-type')).toContain('application/json');
    expect(response.headers.get('server-timing')).toContain('total;dur=4.2');
    expect(response.headers.get('x-cache')).toBe('HIT');
    expect(response.headers.get('x-search-semantic-cache')).toBe('HIT');
    expect(await response.json()).toEqual(mockSearchResponse);
  });

  it('uses a client-supplied API key as API-client traffic', async () => {
    const request = new Request(
      'https://example.com/search/results?q=maps&page=2&per_page=10',
      {
        headers: {
          Accept: 'application/vnd.api+json, application/json',
          'X-API-Key': 'client-k6-key',
          'X-BTAA-Client-Channel': 'browser',
          'X-Visit-Token': 'visit-123',
        },
      }
    );

    vi.mocked(serverFetchWithTheme).mockResolvedValue(
      new Response(JSON.stringify(mockSearchResponse), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
        },
      })
    );

    await loader({
      request,
      params: {},
    } as unknown as LoaderFunctionArgs);

    const [, , options] = vi.mocked(serverFetchWithTheme).mock.calls[0];
    const headers = options?.headers as Headers;

    expect(headers.get('x-api-key')).toBe('client-k6-key');
    expect(headers.get('x-btaa-turnstile-gate')).toBeNull();
    expect(headers.get('x-btaa-client-channel')).toBeNull();
  });

  it('forwards only the Turnstile cookie when browser storage lacks the session header', async () => {
    const request = {
      url: 'https://example.com/search/results?q=maps',
      headers: new Headers({
        cookie:
          'rui.theme=btaa; btaa_turnstile_session=session-123; other=skip',
        'X-BTAA-Client-Channel': 'browser',
      }),
    } as Request;

    vi.mocked(serverFetchWithTheme).mockResolvedValue(
      new Response(JSON.stringify(mockSearchResponse), {
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
        },
      })
    );

    await loader({
      request,
      params: {},
    } as unknown as LoaderFunctionArgs);

    const [, , options] = vi.mocked(serverFetchWithTheme).mock.calls[0];
    const headers = options?.headers as Headers;

    expect(headers.get('x-btaa-turnstile-gate')).toBe('frontend-search');
    expect(headers.get('cookie')).toBe('btaa_turnstile_session=session-123');
  });

  it('returns 500 when upstream fetch fails', async () => {
    const request = new Request('https://example.com/search/results?q=maps');
    vi.mocked(serverFetchWithTheme).mockRejectedValue(new Error('nope'));

    const response = await loader({
      request,
      params: {},
    } as unknown as LoaderFunctionArgs);

    expect(response.status).toBe(500);
    expect(await response.text()).toBe('Failed to fetch search results');
  });
});

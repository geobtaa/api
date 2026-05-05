import type { LoaderFunctionArgs } from 'react-router';
import { serverFetch } from '../lib/server-api';

const FORWARDED_RESPONSE_HEADERS = [
  'cache-control',
  'content-type',
  'etag',
  'last-modified',
  'vary',
  'x-cache',
] as const;

function emptyResponse(query: string, limit: number): Response {
  return new Response(
    JSON.stringify({
      jsonapi: { version: '1.1', profile: [] },
      links: { self: '' },
      meta: {
        totalCount: 0,
        totalPages: 0,
        currentPage: 1,
        perPage: limit,
        query,
        offset: 0,
        gazetteer: 'nominatim',
      },
      data: [],
    }),
    {
      status: 200,
      headers: {
        'content-type': 'application/json; charset=utf-8',
        'cache-control': 'public, max-age=300',
      },
    }
  );
}

function normalizeQuery(query: string): string {
  return query.trim().replace(/\s+/g, ' ');
}

function normalizeLimit(limit: string | null): number {
  const parsed = Number.parseInt(limit || '5', 10);
  return Number.isFinite(parsed) ? Math.max(1, Math.min(parsed, 5)) : 5;
}

function copyUpstreamHeaders(source: Headers): Headers {
  const headers = new Headers();

  FORWARDED_RESPONSE_HEADERS.forEach((name) => {
    const value = source.get(name);
    if (value) headers.set(name, value);
  });

  if (!headers.has('content-type')) {
    headers.set('content-type', 'application/json; charset=utf-8');
  }

  return headers;
}

export async function loader({ request }: LoaderFunctionArgs) {
  const requestUrl = new URL(request.url);
  const query = normalizeQuery(requestUrl.searchParams.get('q') || '');
  const limit = normalizeLimit(requestUrl.searchParams.get('limit'));

  if (!query) {
    return emptyResponse('', limit);
  }

  const upstreamUrl = new URL(
    '/gazetteers/nominatim/search',
    'http://placeholder'
  );
  upstreamUrl.searchParams.set('q', query);
  upstreamUrl.searchParams.set('limit', limit.toString());

  const headers = new Headers({
    Accept: 'application/vnd.api+json, application/json',
  });
  const acceptLanguage = request.headers.get('accept-language');
  if (acceptLanguage) {
    headers.set('accept-language', acceptLanguage);
  }

  const upstream = await serverFetch(
    `${upstreamUrl.pathname}${upstreamUrl.search}`,
    { headers }
  );

  const body = await upstream.arrayBuffer();
  const responseHeaders = copyUpstreamHeaders(upstream.headers);
  responseHeaders.delete('content-encoding');
  responseHeaders.delete('content-length');

  return new Response(body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

import type { LoaderFunctionArgs } from 'react-router';
import { serverFetchWithTheme } from '../lib/server-api';

const FORWARDED_RESPONSE_HEADERS = [
  'cache-control',
  'content-type',
  'etag',
  'last-modified',
  'server-timing',
  'vary',
  'x-cache',
  'x-search-semantic-cache',
] as const;

const FORWARDED_REQUEST_HEADERS = [
  'accept',
  'authorization',
  'x-api-key',
  'x-btaa-client-name',
  'x-btaa-client-channel',
  'x-btaa-client-version',
  'x-visit-token',
  'x-turnstile-session',
] as const;

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

function copyBrowserContextHeaders(source: Headers): Headers {
  const headers = new Headers();
  const authHeader = source.get('authorization') || '';
  const hasClientApiKey =
    Boolean(source.get('x-api-key')) || authHeader.startsWith('Bearer ');

  FORWARDED_REQUEST_HEADERS.forEach((name) => {
    const value = source.get(name);
    if (value) headers.set(name, value);
  });

  if (!hasClientApiKey) {
    headers.set('x-btaa-turnstile-gate', 'frontend-search');
  } else {
    headers.delete('x-btaa-turnstile-gate');
    headers.delete('x-btaa-client-channel');
  }

  return headers;
}

/**
 * Browser-facing search data proxy.
 *
 * The browser requests /search/results?... after the shell renders. This loader
 * calls the upstream /api/v1/search endpoint with the server-only API key while
 * preserving the exact JSON payload shape returned by the backend.
 */
export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const upstreamPath = '/search';
  const upstreamUrl = new URL(upstreamPath, 'http://placeholder');

  url.searchParams.forEach((value, key) => {
    upstreamUrl.searchParams.append(key, value);
  });

  try {
    const pathAndQuery = `${upstreamPath}${upstreamUrl.search}`;
    const upstreamResponse = await serverFetchWithTheme(request, pathAndQuery, {
      headers: copyBrowserContextHeaders(request.headers),
    });

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      headers: copyUpstreamHeaders(upstreamResponse.headers),
    });
  } catch (error) {
    console.error('Search results proxy error:', error);
    if (error instanceof Response) {
      return error;
    }
    return new Response('Failed to fetch search results', { status: 500 });
  }
}

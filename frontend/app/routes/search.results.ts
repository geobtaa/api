import type { LoaderFunctionArgs } from 'react-router';
import { serverFetchWithTheme } from '../lib/server-api';

// Minimal Node-ish env typing without pulling in @types/node.
declare const process: { env: Record<string, string | undefined> };

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

const TURNSTILE_COOKIE_NAME = 'btaa_turnstile_session';

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

function copyBrowserContextHeaders(source: Headers, requestUrl: URL): Headers {
  const headers = new Headers();
  const authHeader = source.get('authorization') || '';
  const hasClientApiKey =
    Boolean(source.get('x-api-key')) || authHeader.startsWith('Bearer ');
  const shouldUseFrontendGate =
    !hasClientApiKey && !shouldBypassLocalTurnstileGate(requestUrl);

  FORWARDED_REQUEST_HEADERS.forEach((name) => {
    const value = source.get(name);
    if (value) headers.set(name, value);
  });

  if (shouldUseFrontendGate) {
    headers.set('x-btaa-turnstile-gate', 'frontend-search');
    if (!headers.has('x-turnstile-session')) {
      const turnstileCookie = extractCookie(
        source.get('cookie'),
        TURNSTILE_COOKIE_NAME
      );
      if (turnstileCookie) {
        headers.set('cookie', `${TURNSTILE_COOKIE_NAME}=${turnstileCookie}`);
      }
    }
  } else {
    stripFrontendGateMarkers(headers);
  }

  return headers;
}

function stripFrontendGateMarkers(headers: Headers) {
  headers.delete('x-btaa-turnstile-gate');
  headers.delete('x-btaa-client-channel');
  headers.delete('x-visit-token');
  headers.delete('cookie');
}

function shouldBypassLocalTurnstileGate(requestUrl: URL): boolean {
  if (isLocalTurnstileEnabled()) return false;

  return isLocalHostname(requestUrl.hostname);
}

function isLocalTurnstileEnabled(): boolean {
  return (
    isEnabledFlag(process.env.VITE_TURNSTILE_ENABLE_LOCAL) ||
    isEnabledFlag(import.meta.env.VITE_TURNSTILE_ENABLE_LOCAL)
  );
}

function isLocalHostname(hostname: string): boolean {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname === '::1' ||
    hostname === '[::1]'
  );
}

function isEnabledFlag(value: string | undefined): boolean {
  return ['1', 'true', 'yes', 'on'].includes(
    String(value || '')
      .trim()
      .toLowerCase()
  );
}

function extractCookie(
  cookieHeader: string | null,
  cookieName: string
): string | null {
  if (!cookieHeader) return null;

  const prefix = `${cookieName}=`;
  const cookie = cookieHeader
    .split(';')
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));

  return cookie ? cookie.slice(prefix.length) : null;
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
      headers: copyBrowserContextHeaders(request.headers, url),
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

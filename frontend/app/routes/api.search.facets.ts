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

/**
 * SSR-served facet values (resource route).
 *
 * The browser requests: /search/facets/{facetName}?...
 * The SSR server fetches from the upstream API using the server-only API key and returns JSON.
 * This ensures the client does not hit rate limits for facet interactions.
 *
 * Note: Route is /search/facets/:facetName (not /api/v1/...) to ensure it goes through SSR
 * and uses the API key, rather than being proxied directly to FastAPI by nginx.
 */
export async function loader({ params, request }: LoaderFunctionArgs) {
  const facetName = params.facetName;

  if (!facetName) {
    throw new Response('facetName is required', { status: 400 });
  }

  const url = new URL(request.url);

  // Construct the upstream URL path
  // The upstream API expects: /search/facets/{facetName}?PARAMS
  // We need to forward relevant query parameters from the client request.
  const upstreamPath = `/search/facets/${facetName}`;
  const upstreamUrl = new URL(upstreamPath, 'http://placeholder'); // Base irrelevant for constructing search params

  // Forward all search parameters from the client request
  url.searchParams.forEach((value, key) => {
    upstreamUrl.searchParams.append(key, value);
  });

  try {
    // serverFetch uses the BTAA_GEOSPATIAL_API_KEY from env
    // and preserves upstream caching semantics when we pass headers through.
    const pathAndQuery = `${upstreamPath}${upstreamUrl.search}`;
    const upstreamResponse = await serverFetch(pathAndQuery);

    return new Response(upstreamResponse.body, {
      status: upstreamResponse.status,
      headers: copyUpstreamHeaders(upstreamResponse.headers),
    });
  } catch (error) {
    console.error('Facet proxy error:', error);
    // Propagate the error status if it's a Response, otherwise 500
    if (error instanceof Response) {
      return error;
    }
    return new Response('Failed to fetch facet values', { status: 500 });
  }
}

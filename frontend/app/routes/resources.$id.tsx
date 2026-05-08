import type { LoaderFunctionArgs, MetaFunction } from 'react-router';
import { useLoaderData } from 'react-router';
import { ResourceView } from '../../src/pages/ResourceView';
import { serverFetchJson } from '../lib/server-api';
import type { GeoDocumentDetails } from '../../src/types/api';
import { useEffect } from 'react';
import { useApi } from '../../src/context/ApiContext';
import { buildSeoMeta } from '../../src/config/seo';
import { GeoportalRouteErrorBoundary } from '../../src/pages/ErrorPage';
import { isGeoportalErrorStatus } from '../../src/pages/errorPageContent';

/**
 * Loader function that runs server-side to fetch resource details.
 * For now, ResourceView fetches its own data, but we can pre-fetch here
 * and pass it as props in the future.
 */
export async function loader({ params, request }: LoaderFunctionArgs) {
  const { id } = params;

  if (!id) {
    throw new Response('Resource ID is required', { status: 400 });
  }

  // Get the full URL for Open Graph tags
  const currentUrl = new URL(request.url).href;

  try {
    const [resourceRes, jsonLdRes] = await Promise.all([
      serverFetchJson<{ data: GeoDocumentDetails }>(
        `/resources/${id}?format=json`
      ),
      serverFetchJson<Record<string, unknown>>(
        `/resources/${id}/citation/json-ld`
      ).catch(() => null),
    ]);

    const lastApiUrl = `/api/v1/resources/${id}?format=json`;
    return {
      resource: resourceRes.data,
      jsonLd: jsonLdRes,
      lastApiUrl,
      currentUrl,
    };
  } catch (error) {
    console.error('Resource loader error:', error);
    if (error instanceof Response && isGeoportalErrorStatus(error.status)) {
      throw error;
    }
    // Allow ResourceView to handle its own errors for now
    const lastApiUrl = `/api/v1/resources/${id}?format=json`;
    return { resource: null, jsonLd: null, lastApiUrl, currentUrl };
  }
}

export function ErrorBoundary() {
  return <GeoportalRouteErrorBoundary />;
}

function resourceDescription(resource: GeoDocumentDetails | null) {
  const desc = resource?.attributes?.ogm?.dct_description_sm;
  if (Array.isArray(desc)) {
    return desc[0] ?? '';
  }
  return typeof desc === 'string' ? desc : '';
}

function resourceOgImage(resource: GeoDocumentDetails | null) {
  const thumbnailUrl = resource?.meta?.ui?.thumbnail_url;
  const isPlaceholderThumbnail =
    !thumbnailUrl ||
    (typeof thumbnailUrl === 'string' && thumbnailUrl.includes('placeholder'));
  const hasStaticMap = Boolean(resource?.meta?.ui?.static_map && resource?.id);

  if (!isPlaceholderThumbnail) {
    return thumbnailUrl;
  }

  if (hasStaticMap) {
    return `/resources/${resource.id}/static-map`;
  }

  return undefined;
}

export const meta: MetaFunction<typeof loader> = ({ data }) => {
  const resource = data?.resource ?? null;
  const descriptors = buildSeoMeta({
    title: resource?.attributes?.ogm?.dct_title_s || 'Resource',
    description: resourceDescription(resource),
    image: resourceOgImage(resource),
    url: data?.currentUrl,
    type: 'article',
  });

  if (data?.jsonLd) {
    descriptors.push({
      'script:ld+json': data.jsonLd as Record<string, unknown> as never,
    });
  }

  return descriptors;
};

/**
 * Resource detail page.
 * ResourceView currently fetches its own data, but loader data is available
 * via useLoaderData() if we want to pre-populate in the future.
 */
export default function Resource() {
  const { resource, lastApiUrl, currentUrl } = useLoaderData() as {
    resource: GeoDocumentDetails | null;
    jsonLd: Record<string, unknown> | null;
    lastApiUrl?: string;
    currentUrl?: string;
  };
  const { setLastApiUrl } = useApi();

  // Keep footer's "Last API Request" in sync with SSR loader calls without re-fetching in the browser.
  useEffect(() => {
    if (lastApiUrl) setLastApiUrl(lastApiUrl);
  }, [lastApiUrl, setLastApiUrl]);

  // Prefer loader data (server-side) to avoid duplicate client fetches.
  return (
    <ResourceView
      prefetchedResource={resource ?? undefined}
      currentUrl={currentUrl}
    />
  );
}

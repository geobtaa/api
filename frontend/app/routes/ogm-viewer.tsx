import {
  useLoaderData,
  type LoaderFunctionArgs,
  type MetaFunction,
} from 'react-router';
import { serverFetchJson } from '../lib/server-api';
import { ResourceViewer } from '../../src/components/resource/ResourceViewer';
import { hasOgmContentPreview } from '../../src/utils/ogmViewerRecord';
import type { GeoDocumentDetails } from '../../src/types/api';

export async function loader({ request }: LoaderFunctionArgs) {
  const params = new URL(request.url).searchParams;
  const resourceId = params.get('resource');
  if (resourceId) {
    const { data } = await serverFetchJson<{ data: GeoDocumentDetails }>(
      `/resources/${encodeURIComponent(resourceId)}?format=json`
    );
    return { resource: data, error: null };
  }

  // Legacy links only have a manifest, with no catalog record identifier.
  const manifest = params.get('manifest');
  try {
    if (
      !manifest ||
      !['http:', 'https:'].includes(new URL(manifest).protocol)
    ) {
      throw new Error('Invalid manifest');
    }
  } catch {
    return {
      resource: null,
      error: 'Provide a resource ID or a valid IIIF manifest URL.',
    };
  }
  return {
    resource: {
      id: manifest,
      attributes: {
        ogm: {
          id: manifest,
          dct_title_s: 'IIIF manifest',
          dct_references_s: {
            'http://iiif.io/api/presentation#manifest': manifest,
          },
        },
      },
    },
    error: null,
  };
}

export const meta: MetaFunction<typeof loader> = ({ data }) => [
  {
    title: `${data?.resource?.attributes.ogm?.dct_title_s || 'Resource'} – OGM Viewer`,
  },
  { name: 'robots', content: 'noindex,nofollow' },
];

export default function OgmViewerRoute() {
  const { resource, error } = useLoaderData<typeof loader>();
  return (
    <main className="fixed inset-0 overflow-hidden bg-white">
      {resource && hasOgmContentPreview(resource) ? (
        <ResourceViewer data={resource} standalone />
      ) : (
        <div
          role="alert"
          className="flex h-full items-center justify-center p-6 text-gray-600"
        >
          {error || 'This resource has no preview available.'}
        </div>
      )}
    </main>
  );
}

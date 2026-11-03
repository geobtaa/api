import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { LoaderFunctionArgs } from 'react-router';
import OgmViewerRoute, { loader } from '../../../app/routes/ogm-viewer';
import { loader as legacyLoader } from '../../../app/routes/mirador';
import { serverFetchJson } from '../../../app/lib/server-api';

const mocks = vi.hoisted(() => ({ data: {} as unknown, viewer: vi.fn() }));
vi.mock('../../../app/lib/server-api', () => ({ serverFetchJson: vi.fn() }));
vi.mock('react-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router')>()),
  useLoaderData: () => mocks.data,
}));
vi.mock('../../components/resource/ResourceViewer', () => ({
  ResourceViewer: (props: unknown) => {
    mocks.viewer(props);
    return <div>OGM canvas</div>;
  },
}));
const args = (query: string) =>
  ({
    request: new Request(`http://localhost/ogm-viewer${query}`),
    params: {},
    context: {},
  }) as LoaderFunctionArgs;
const manifest = 'https://example.org/book/manifest.json?key=a%2Fb&lang=en';

beforeEach(() => vi.clearAllMocks());

describe('standalone OGM Viewer', () => {
  it('permanently redirects old URLs without losing encoded manifest parameters', () => {
    const query = `?manifest=${encodeURIComponent(manifest)}&embedded=1`;
    const response = legacyLoader(args(query));
    expect(response.status).toBe(301);
    expect(response.headers.get('Location')).toBe(`/ogm-viewer${query}`);
  });

  it('loads the full catalog record and passes it to the standalone viewer', async () => {
    const resource = {
      id: 'collection:1',
      attributes: {
        ogm: {
          dct_title_s: 'Book',
          dct_references_s: {
            'http://iiif.io/api/presentation#manifest': manifest,
          },
        },
      },
    };
    vi.mocked(serverFetchJson).mockResolvedValue({ data: resource });
    mocks.data = await loader(args('?resource=collection%3A1'));
    render(<OgmViewerRoute />);
    expect(serverFetchJson).toHaveBeenCalledWith(
      '/resources/collection%3A1?format=json'
    );
    expect(mocks.viewer).toHaveBeenCalledWith({
      data: resource,
      standalone: true,
    });
  });

  it('supports bookmarked manifest-only links without fetching external URLs on the server', async () => {
    const result = await loader(
      args(`?manifest=${encodeURIComponent(manifest)}`)
    );
    expect(result.resource?.attributes.ogm?.dct_references_s).toEqual({
      'http://iiif.io/api/presentation#manifest': manifest,
    });
    expect(serverFetchJson).not.toHaveBeenCalled();
    mocks.data = result;
    render(<OgmViewerRoute />);
    expect(screen.getByText('OGM canvas')).toBeInTheDocument();
  });

  it.each(['', '?manifest=invalid', '?manifest=javascript%3Aalert(1)'])(
    'reports missing or invalid inputs (%s)',
    async (query) => {
      mocks.data = await loader(args(query));
      render(<OgmViewerRoute />);
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Provide a resource ID or a valid IIIF manifest URL.'
      );
      expect(mocks.viewer).not.toHaveBeenCalled();
      expect(serverFetchJson).not.toHaveBeenCalled();
    }
  );

  it('shows a message instead of a blank canvas for location-only records', async () => {
    vi.mocked(serverFetchJson).mockResolvedValue({
      data: {
        id: 'location',
        attributes: { ogm: { locn_geometry: 'ENVELOPE(-90,-89,45,44)' } },
      },
    });
    mocks.data = await loader(args('?resource=location'));
    render(<OgmViewerRoute />);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'This resource has no preview available.'
    );
    expect(mocks.viewer).not.toHaveBeenCalled();
  });

  it('propagates missing-record errors to the route boundary', async () => {
    const error = new Response('Not found', { status: 404 });
    vi.mocked(serverFetchJson).mockRejectedValue(error);
    await expect(loader(args('?resource=missing'))).rejects.toBe(error);
  });
});

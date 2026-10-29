import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  recordConstructor: vi.fn(function MockOgmRecord(
    this: { json?: Record<string, unknown> },
    data: Record<string, unknown>
  ) {
    this.json = data;
  }),
}));

vi.mock('ogm-viewer', () => ({}));
vi.mock('ogm-viewer/lib', () => ({
  OgmRecord: mocks.recordConstructor,
}));

import { ResourceViewer } from '../../../components/resource/ResourceViewer';

const PMTILES_REFERENCE = 'https://github.com/protomaps/PMTiles';
const WMS_REFERENCE = 'http://www.opengis.net/def/serviceType/ogc/wms';

function viewerData(id: string, references: string | Record<string, unknown>) {
  return {
    id,
    attributes: {
      ogm: {
        id,
        dct_title_s: `Resource ${id}`,
        gbl_resourceClass_sm: ['Datasets'],
        dct_accessRights_s: 'Public',
        gbl_mdVersion_s: 'Aardvark',
        gbl_wxsIdentifier_s: 'example-layer',
        dct_references_s: references,
      },
    },
  } as Parameters<typeof ResourceViewer>[0]['data'];
}

describe('ResourceViewer', () => {
  beforeAll(() => {
    if (!customElements.get('ogm-viewer')) {
      customElements.define(
        'ogm-viewer',
        class extends HTMLElement {
          private currentRecord?: unknown;

          get loadedRecord() {
            return this.currentRecord;
          }

          async loadRecord(record: unknown) {
            this.currentRecord = record;
            this.dispatchEvent(new CustomEvent('previewsLoading'));
            queueMicrotask(() => {
              this.dispatchEvent(new CustomEvent('previewsLoaded'));
            });
          }
        }
      );
    }
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('loads the Aardvark record into the full OGM viewer', async () => {
    const references = {
      [PMTILES_REFERENCE]: 'https://example.com/resource.pmtiles',
    };
    const { container } = render(
      <ResourceViewer data={viewerData('resource-1', references)} />
    );

    expect(screen.getByRole('status')).toHaveTextContent('Loading viewer…');
    expect(container.querySelector('ogm-viewer')).not.toHaveClass('hidden');

    await waitFor(() => expect(mocks.recordConstructor).toHaveBeenCalled());

    expect(container.querySelector('ogm-viewer')).toHaveAttribute(
      'light-basemap',
      'https://tiles.openfreemap.org/styles/liberty'
    );
    expect(mocks.recordConstructor).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'resource-1',
        gbl_mdVersion_s: 'Aardvark',
        dct_references_s: JSON.stringify(references),
      })
    );

    const viewer = container.querySelector('ogm-viewer') as HTMLElement & {
      loadedRecord?: unknown;
    };
    expect(viewer.loadedRecord).toBe(mocks.recordConstructor.mock.instances[0]);
    expect(viewer).toHaveAttribute('theme', 'light');
    expect(viewer).toHaveClass('h-[600px]');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('preserves serialized references and replaces the record when data changes', async () => {
    const firstReferences = JSON.stringify({
      [WMS_REFERENCE]: 'https://example.com/first/wms',
    });
    const secondReferences = JSON.stringify({
      [WMS_REFERENCE]: 'https://example.com/second/wms',
    });
    const { container, rerender } = render(
      <ResourceViewer data={viewerData('resource-1', firstReferences)} />
    );

    await waitFor(() =>
      expect(mocks.recordConstructor).toHaveBeenCalledTimes(1)
    );
    expect(mocks.recordConstructor).toHaveBeenLastCalledWith(
      expect.objectContaining({ dct_references_s: firstReferences })
    );

    rerender(
      <ResourceViewer data={viewerData('resource-2', secondReferences)} />
    );

    await waitFor(() =>
      expect(mocks.recordConstructor).toHaveBeenCalledTimes(2)
    );
    expect(mocks.recordConstructor).toHaveBeenLastCalledWith(
      expect.objectContaining({
        id: 'resource-2',
        dct_references_s: secondReferences,
      })
    );

    const viewer = container.querySelector('ogm-viewer') as HTMLElement & {
      loadedRecord?: unknown;
    };
    expect(viewer.loadedRecord).toBe(mocks.recordConstructor.mock.instances[1]);
  });

  it('shows an accessible fallback when the OGM record cannot be loaded', async () => {
    const consoleError = vi
      .spyOn(console, 'error')
      .mockImplementation(() => {});
    mocks.recordConstructor.mockImplementationOnce(function BrokenOgmRecord() {
      throw new Error('Invalid record');
    });

    render(<ResourceViewer data={viewerData('broken', {})} />);

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Item viewer unavailable.'
    );
    expect(consoleError).toHaveBeenCalledWith(
      'Failed to load OGM viewer:',
      expect.any(Error)
    );

    consoleError.mockRestore();
  });
});

it('follows the active preview, caches hidden images, clears transitions and ignores old records', async () => {
  const onChange = vi.fn();
  const data = viewerData('record', {});
  const { container, rerender, unmount } = render(
    <ResourceViewer data={data} onImageSelectionChange={onChange} />
  );
  await waitFor(() =>
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  );
  const viewer = container.querySelector('ogm-viewer')!;
  const first = {
    previewId: 'first',
    resourceId: 'record',
    resourceUrl: 'https://example.org/manifest',
    renderer: 'image',
  };
  const second = { ...first, previewId: 'second' };
  const image = {
    url: 'https://example.org/iiif/1/info.json',
    index: 0,
    count: 2,
  };
  const emit = (name: string, detail: unknown) =>
    act(() => {
      viewer.dispatchEvent(new CustomEvent(name, { detail }));
    });
  emit('imageChange', { ...first, image });
  emit('previewChange', first);
  expect(onChange).toHaveBeenLastCalledWith({ ...first, image });
  emit('imageChange', { ...second, image: { ...image, index: 1 } });
  expect(onChange).toHaveBeenLastCalledWith({ ...first, image });
  emit('previewChange', second);
  expect(onChange.mock.lastCall?.[0].image.index).toBe(1);
  emit('imageChange', { ...second, image: null });
  expect(onChange.mock.lastCall?.[0].image).toBeNull();
  emit('previewChange', { ...first, renderer: 'map' });
  expect(onChange).toHaveBeenLastCalledWith(null);
  emit('previewChange', { ...first, resourceId: 'old-record' });
  expect(onChange).toHaveBeenLastCalledWith(null);
  rerender(
    <ResourceViewer
      data={viewerData('new-record', {})}
      onImageSelectionChange={onChange}
    />
  );
  await waitFor(() =>
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  );
  emit('imageChange', { ...first, image });
  emit('previewChange', first);
  expect(onChange).toHaveBeenLastCalledWith(null);
  unmount();
  const calls = onChange.mock.calls.length;
  emit('imageChange', { ...first, image });
  expect(onChange).toHaveBeenCalledTimes(calls);
});

it('sends picker navigation to the public viewer host only for the active sequence', async () => {
  const data = viewerData('record', {});
  const { container, rerender } = render(<ResourceViewer data={data} />);
  await waitFor(() =>
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  );
  const viewer = container.querySelector('ogm-viewer')!;
  const preview = {
    previewId: 'preview',
    resourceId: 'record',
    resourceUrl: 'https://example.org/manifest',
    renderer: 'image' as const,
  };
  const page = {
    url: 'https://example.org/page/info.json',
    index: 2,
    occurrence: 0,
  };
  act(() => {
    viewer.dispatchEvent(new CustomEvent('previewChange', { detail: preview }));
    viewer.dispatchEvent(
      new CustomEvent('imageChange', {
        detail: {
          ...preview,
          sequence: [page],
          pageIndex: 2,
          image: { ...page, count: 3 },
        },
      })
    );
  });
  const navigate = vi.fn();
  viewer.addEventListener('imageNavigationRequest', navigate);
  const request = { ...preview, index: page.index, url: page.url };
  rerender(<ResourceViewer data={data} imageNavigation={request} />);
  expect(navigate).toHaveBeenCalledTimes(1);
  expect(navigate.mock.lastCall?.[0].detail).toEqual(request);
  for (const invalid of [
    { ...request, previewId: 'hidden' },
    { ...request, resourceId: 'old' },
    { ...request, index: 1 },
    { ...request, url: 'https://example.org/old' },
  ]) {
    rerender(<ResourceViewer data={data} imageNavigation={invalid} />);
  }
  expect(navigate).toHaveBeenCalledTimes(1);
  act(() =>
    viewer.dispatchEvent(
      new CustomEvent('previewChange', {
        detail: { ...preview, renderer: 'map' },
      })
    )
  );
  rerender(<ResourceViewer data={data} imageNavigation={{ ...request }} />);
  expect(navigate).toHaveBeenCalledTimes(1);
});

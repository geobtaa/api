import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  setAssetBase: vi.fn(),
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
vi.mock('ogm-viewer/components/p-BbMGvQFJ.js', () => ({
  s: mocks.setAssetBase,
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

    await waitFor(() => expect(mocks.recordConstructor).toHaveBeenCalled());

    expect(mocks.setAssetBase).toHaveBeenCalledWith('/ogm-viewer/');
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

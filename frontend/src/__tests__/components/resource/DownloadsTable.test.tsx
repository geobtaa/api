import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { DownloadsTable } from '../../../components/resource/DownloadsTable';

vi.mock('../../../services/analytics', () => ({
  scheduleAnalyticsBatch: vi.fn(),
}));

describe('DownloadsTable', () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  const pageDownloads = [
    {
      label: 'Small Image',
      url: 'https://example.org/1.jpg',
      type: 'image/jpeg',
      source: 'iiif',
      canvas_id: 'page-1',
      canvas_label: 'Cover',
    },
    {
      label: 'Download Image',
      url: 'https://example.org/2.png',
      type: 'image/png',
      source: 'iiif',
      canvas_id: 'page-2',
      canvas_label: 'Map',
    },
    {
      label: 'Atlas PDF',
      url: 'https://example.org/atlas.pdf',
      type: 'application/pdf',
      source: 'iiif',
    },
  ];

  it('loads manifest-only downloads and switches pages without hiding whole-item files', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ downloads: pageDownloads }),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<DownloadsTable downloads={[]} resourceId="atlas:1" resolveIiif />);
    expect(screen.getByRole('status')).toHaveTextContent(
      'Loading image downloads'
    );
    const selector = await screen.findByRole('combobox', {
      name: 'Page or sheet (2)',
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/resources/atlas%3A1/downloads',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
    expect(screen.getByRole('link', { name: 'Small' })).toHaveAttribute(
      'href',
      'https://example.org/1.jpg'
    );
    expect(
      screen.queryByRole('link', { name: 'Download' })
    ).not.toBeInTheDocument();
    fireEvent.change(selector, { target: { value: 'page-2' } });
    expect(screen.getByRole('link', { name: 'Download' })).toHaveAttribute(
      'href',
      'https://example.org/2.png'
    );
    expect(
      screen.queryByRole('link', { name: 'Small' })
    ).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Atlas PDF' })).toBeInTheDocument();
  });

  it('shows a single image without a page selector', () => {
    render(<DownloadsTable downloads={[pageDownloads[0]]} />);
    expect(screen.getByText('Download Image')).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('preserves ordinary downloads on failure and retries IIIF resolution', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error('Provider unavailable'))
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ downloads: pageDownloads }),
      });
    vi.stubGlobal('fetch', fetchMock);
    render(
      <DownloadsTable
        downloads={[
          { label: 'Original PDF', url: 'https://example.org/original.pdf' },
        ]}
        resourceId="atlas"
        resolveIiif
      />
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Retry' }));
    expect(
      screen.getByRole('link', { name: 'Original PDF' })
    ).toBeInTheDocument();
    expect(await screen.findByRole('combobox')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('offers retry when the API reports an unavailable IIIF provider', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ downloads: [], iiif_error: true }),
      })
    );
    render(<DownloadsTable downloads={[]} resourceId="atlas" resolveIiif />);
    expect(
      await screen.findByRole('button', { name: 'Retry' })
    ).toBeInTheDocument();
  });

  it('aborts stale requests when navigating to another resource', async () => {
    let finishOld: (value: unknown) => void = () => {};
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            finishOld = resolve;
          })
      )
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ downloads: [pageDownloads[1]] }),
      });
    vi.stubGlobal('fetch', fetchMock);
    const view = render(
      <DownloadsTable downloads={[]} resourceId="old" resolveIiif />
    );
    const signal = fetchMock.mock.calls[0][1].signal;
    view.rerender(
      <DownloadsTable downloads={[]} resourceId="new" resolveIiif />
    );
    expect(signal.aborted).toBe(true);
    await screen.findByRole('link', { name: 'Download' });
    finishOld({
      ok: true,
      json: async () => ({ downloads: [pageDownloads[0]] }),
    });
    await waitFor(() =>
      expect(
        screen.queryByRole('link', { name: 'Small' })
      ).not.toBeInTheDocument()
    );
  });

  it('does not fetch IIIF for ordinary records', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const view = render(
      <DownloadsTable downloads={[]} resourceId="ordinary" />
    );
    expect(view.container).toBeEmptyDOMElement();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('renders generated download labels', () => {
    render(
      <DownloadsTable
        downloads={[
          {
            label: 'EPSG:4326 Shapefile',
            url: '/api/v1/resources/stanford-bs024ty5255/downloads/generated/shapefile',
            type: 'application/zip',
            generated: true,
            generation_path:
              '/api/v1/resources/stanford-bs024ty5255/downloads/generated/shapefile',
          },
        ]}
      />
    );

    expect(screen.getByText('EPSG:4326 Shapefile')).toBeInTheDocument();
  });

  it('prepares and opens generated downloads on click', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: {
        get: (name: string) =>
          name.toLowerCase() === 'content-type' ? 'application/json' : null,
      },
      json: async () => ({
        download_url:
          '/api/v1/resources/stanford-bs024ty5255/downloads/generated/shapefile/file',
      }),
    });
    const openMock = vi.fn();

    const originalFetch = global.fetch;
    const originalOpen = window.open;
    global.fetch = fetchMock as unknown as typeof fetch;
    window.open = openMock as typeof window.open;

    try {
      render(
        <DownloadsTable
          downloads={[
            {
              label: 'EPSG:4326 Shapefile',
              url: '/api/v1/resources/stanford-bs024ty5255/downloads/generated/shapefile',
              type: 'application/zip',
              generated: true,
              generation_path:
                '/api/v1/resources/stanford-bs024ty5255/downloads/generated/shapefile',
            },
          ]}
        />
      );

      fireEvent.click(screen.getByText('EPSG:4326 Shapefile'));

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          expect.stringContaining(
            '/api/v1/resources/stanford-bs024ty5255/downloads/generated/shapefile'
          ),
          expect.objectContaining({
            headers: { Accept: 'application/json' },
          })
        );
      });
      expect(openMock).toHaveBeenCalledWith(
        expect.stringContaining(
          '/api/v1/resources/stanford-bs024ty5255/downloads/generated/shapefile/file'
        ),
        '_blank',
        'noopener,noreferrer'
      );
    } finally {
      global.fetch = originalFetch;
      window.open = originalOpen;
    }
  });
});

it('matches current image source rather than canvas position and hides stale links', () => {
  const manifest = 'https://example.org/manifest';
  const downloads = [
    {
      label: 'First image',
      url: 'https://example.org/one.jpg',
      type: 'image/jpeg',
      source: 'iiif',
      canvas_id: 'same-canvas',
      canvas_label: 'Two scans',
      image_source: 'https://example.org/iiif/one',
      iiif_resource_url: manifest,
    },
    {
      label: 'Second image',
      url: 'https://example.org/two.jpg',
      type: 'image/jpeg',
      source: 'iiif',
      canvas_id: 'same-canvas',
      image_source: 'https://example.org/iiif/two',
      iiif_resource_url: manifest,
    },
    {
      label: 'Sheet PDF',
      url: 'https://example.org/sheet.pdf',
      source: 'iiif',
      canvas_id: 'same-canvas',
      iiif_resource_url: manifest,
    },
    { label: 'Original TIFF', url: 'https://example.org/original.tif' },
  ];
  const selection = {
    resourceId: 'record',
    previewId: 'preview',
    resourceUrl: manifest,
    renderer: 'image' as const,
    image: {
      url: 'https://example.org/iiif/two/info.json',
      index: 4,
      count: 7,
    },
  };
  const { rerender } = render(
    <DownloadsTable
      downloads={downloads}
      resourceId="record"
      followViewer
      activeImage={selection}
    />
  );
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  expect(
    screen.queryByRole('link', { name: 'First image' })
  ).not.toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Second image' })).toHaveAttribute(
    'href',
    downloads[1].url
  );
  expect(screen.getByRole('link', { name: 'Sheet PDF' })).toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Image 5 of 7');
  for (const activeImage of [
    null,
    { ...selection, image: null },
    { ...selection, resourceUrl: 'https://example.org/other' },
    { ...selection, resourceId: 'previous-record' },
    {
      ...selection,
      image: {
        ...selection.image,
        url: 'https://example.org/unknown/info.json',
      },
    },
  ]) {
    rerender(
      <DownloadsTable
        downloads={downloads}
        resourceId="record"
        followViewer
        activeImage={activeImage}
      />
    );
    expect(
      screen.queryByRole('link', { name: 'Second image' })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Sheet PDF' })
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Original TIFF' })
    ).toBeInTheDocument();
  }
  rerender(
    <DownloadsTable
      downloads={downloads}
      resourceId="record"
      followViewer
      activeImage={{
        ...selection,
        image: {
          ...selection.image,
          url: 'https://example.org/iiif/one/info.json',
          index: 0,
        },
      }}
    />
  );
  expect(screen.getByRole('link', { name: 'First image' })).toBeInTheDocument();
});

it('keeps manifest-wide image renderings available without an active canvas', () => {
  render(
    <DownloadsTable
      resourceId="record"
      followViewer
      downloads={[
        {
          label: 'Whole atlas image',
          url: 'https://example.org/atlas.jpg',
          type: 'image/jpeg',
          source: 'iiif',
          iiif_resource_url: 'https://example.org/manifest',
        },
      ]}
    />
  );
  expect(
    screen.getByRole('link', { name: 'Whole atlas image' })
  ).toHaveAttribute('href', 'https://example.org/atlas.jpg');
});

it('distinguishes repeated scans on different canvases using source occurrence', () => {
  const common = {
    label: 'Small Image',
    url: 'https://example.org/scan.jpg',
    type: 'image/jpeg',
    source: 'iiif',
    image_source: 'https://example.org/scan',
    iiif_resource_url: 'https://example.org/manifest',
  };
  const downloads = [
    {
      ...common,
      canvas_id: 'first',
      canvas_label: 'First use',
      image_occurrences: [0],
    },
    {
      ...common,
      canvas_id: 'second',
      canvas_label: 'Second use',
      image_occurrences: [1],
    },
    {
      label: 'Second sheet PDF',
      url: 'https://example.org/second.pdf',
      source: 'iiif',
      canvas_id: 'second',
      iiif_resource_url: common.iiif_resource_url,
    },
  ];
  const selection = {
    previewId: 'preview',
    resourceId: 'record',
    resourceUrl: common.iiif_resource_url,
    renderer: 'image' as const,
    image: {
      url: common.image_source + '/info.json',
      index: 7,
      count: 10,
      occurrence: 1,
    },
  };
  const { rerender } = render(
    <DownloadsTable
      downloads={downloads}
      resourceId="record"
      followViewer
      activeImage={selection}
    />
  );
  expect(screen.getByRole('status')).toHaveTextContent('Second use');
  expect(screen.getAllByRole('link', { name: 'Small' })).toHaveLength(1);
  expect(
    screen.getByRole('link', { name: 'Second sheet PDF' })
  ).toBeInTheDocument();
  rerender(
    <DownloadsTable
      downloads={downloads}
      resourceId="record"
      followViewer
      activeImage={{
        ...selection,
        image: { ...selection.image, occurrence: 0 },
      }}
    />
  );
  expect(screen.getByRole('status')).toHaveTextContent('First use');
  expect(
    screen.queryByRole('link', { name: 'Second sheet PDF' })
  ).not.toBeInTheDocument();
});

it('uses the viewer sequence for a two-way picker, retaining its selection while images load', () => {
  const onImageNavigate = vi.fn();
  const source = 'https://example.org/scan';
  const manifest = 'https://example.org/manifest';
  const sequence = [
    { url: source + '/info.json', index: 0, occurrence: 0 },
    { url: source + '/info.json', index: 7, occurrence: 1 },
  ];
  const downloads = [
    {
      label: 'First scan',
      url: source + '/first.jpg',
      source: 'iiif',
      canvas_id: 'one',
      canvas_label: 'Cover',
      image_source: source,
      image_occurrences: [0],
      iiif_resource_url: manifest,
    },
    {
      label: 'Second scan',
      url: source + '/second.jpg',
      source: 'iiif',
      canvas_id: 'two',
      canvas_label: 'Map sheet',
      image_source: source,
      image_occurrences: [1],
      iiif_resource_url: manifest,
    },
  ];
  const active = {
    previewId: 'preview',
    resourceId: 'record',
    resourceUrl: manifest,
    renderer: 'image' as const,
    sequence,
    pageIndex: 0,
    image: { ...sequence[0], count: 8 },
  };
  const props = {
    downloads,
    resourceId: 'record',
    followViewer: true,
    onImageNavigate,
  };
  const { rerender } = render(
    <DownloadsTable {...props} activeImage={active} />
  );
  const picker = screen.getByRole('combobox', { name: 'Page or sheet (2)' });
  expect(picker).toHaveValue('0');
  expect(screen.getByRole('option', { name: '8. Map sheet' })).toHaveValue('7');
  fireEvent.change(picker, { target: { value: '7' } });
  expect(onImageNavigate).toHaveBeenCalledExactlyOnceWith({
    previewId: 'preview',
    resourceId: 'record',
    resourceUrl: manifest,
    renderer: 'image',
    index: 7,
    url: sequence[1].url,
  });
  expect(screen.getByRole('link', { name: 'First scan' })).toBeInTheDocument();
  rerender(
    <DownloadsTable
      {...props}
      activeImage={{ ...active, pageIndex: 7, image: null }}
    />
  );
  expect(picker).toHaveValue('7');
  expect(
    screen.queryByRole('link', { name: 'First scan' })
  ).not.toBeInTheDocument();
  rerender(
    <DownloadsTable
      {...props}
      activeImage={{
        ...active,
        pageIndex: 7,
        image: { ...sequence[1], count: 8 },
      }}
    />
  );
  expect(screen.getByRole('link', { name: 'Second scan' })).toBeInTheDocument();
  rerender(<DownloadsTable {...props} activeImage={active} />);
  expect(picker).toHaveValue('0');
  expect(onImageNavigate).toHaveBeenCalledTimes(1);
});

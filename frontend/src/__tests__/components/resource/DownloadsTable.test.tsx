import React from 'react';
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

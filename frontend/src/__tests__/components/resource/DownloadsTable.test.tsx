import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { DownloadsTable } from '../../../components/resource/DownloadsTable';

vi.mock('../../../services/analytics', () => ({
  scheduleAnalyticsBatch: vi.fn(),
}));

describe('DownloadsTable', () => {
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

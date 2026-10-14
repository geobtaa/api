import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { LoaderFunctionArgs } from 'react-router';
import { loader } from '../resources.$id.thumbnail';

vi.mock('../../lib/server-api', () => ({
  serverFetch: vi.fn(),
}));

import { serverFetch } from '../../lib/server-api';

describe('resource thumbnail loader', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('preserves pending and no-store headers so browser recovery can retry', async () => {
    vi.mocked(serverFetch).mockResolvedValue(
      new Response('<svg/>', {
        headers: {
          'Content-Type': 'image/svg+xml',
          'X-Thumbnail-Pending': 'true',
          'Retry-After': '2',
          'Cache-Control': 'no-store',
        },
      })
    );
    const response = await loader({
      params: { id: 'result-1' },
      request: new Request('https://geo.btaa.org/resources/result-1/thumbnail'),
    } as LoaderFunctionArgs);
    expect(response.headers.get('X-Thumbnail-Pending')).toBe('true');
    expect(response.headers.get('Retry-After')).toBe('2');
    expect(response.headers.get('Cache-Control')).toBe('no-store');
    expect(await response.text()).toBe('<svg/>');
  });

  it('forwards the icon-gradient variant used by list-view fallbacks', async () => {
    vi.mocked(serverFetch).mockResolvedValue(
      new Response('<svg></svg>', {
        headers: { 'Content-Type': 'image/svg+xml' },
      })
    );

    const response = await loader({
      params: { id: 'result-1' },
      request: new Request(
        'https://geo.btaa.org/resources/result-1/thumbnail?variant=icon-gradient'
      ),
    } as LoaderFunctionArgs);

    expect(serverFetch).toHaveBeenCalledWith(
      '/resources/result-1/thumbnail?variant=icon-gradient',
      {
        headers: { Accept: 'image/*,*/*;q=0.8' },
        redirect: 'manual',
      }
    );
    expect(response.headers.get('content-type')).toBe('image/svg+xml');
    expect(await response.text()).toBe('<svg></svg>');
  });
});

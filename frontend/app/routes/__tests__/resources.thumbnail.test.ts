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

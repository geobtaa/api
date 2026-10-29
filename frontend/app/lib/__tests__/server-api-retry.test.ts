import { expect, it, vi } from 'vitest';
import { serverFetchJson, serverFetchJsonWithTheme } from '../server-api';
vi.mock('../theme.server', () => ({ getThemeConfigFromRequest: () => ({}) }));
it.each(['plain', 'theme'])(
  'preserves upstream retry guidance for %s API errors',
  async (mode) => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response('throttled', {
            status: 429,
            headers: { 'Retry-After': '30' },
          })
        )
    );
    const error = await (
      mode === 'plain'
        ? serverFetchJson('/map/h3')
        : serverFetchJsonWithTheme(
            new Request('https://example.com/map/h3'),
            '/map/h3'
          )
    ).catch((error) => error);
    expect(error).toBeInstanceOf(Response);
    expect(error.status).toBe(429);
    expect(error.headers.get('Retry-After')).toBe('30');
    expect(error.headers.get('Cache-Control')).toBe('no-store');
  }
);

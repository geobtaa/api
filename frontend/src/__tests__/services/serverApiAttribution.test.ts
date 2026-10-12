import { afterEach, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  vi.resetModules();
});

it('sends the server key and SSR identity without overwriting browser attribution', async () => {
  vi.stubEnv('BTAA_GEOSPATIAL_API_KEY', 'test-only-key');
  vi.resetModules();
  const fetchMock = vi.fn().mockResolvedValue(new Response('{}'));
  vi.stubGlobal('fetch', fetchMock);
  const { serverFetch } = await import('../../../app/lib/server-api');
  await serverFetch('/search?page=2');
  let headers = fetchMock.mock.calls[0][1].headers as Headers;
  expect(headers.get('X-API-Key')).toBe('test-only-key');
  expect(headers.get('X-BTAA-Client-Name')).toBe('geoportal-ssr');
  expect(headers.get('X-BTAA-Client-Channel')).toBe('ssr');
  await serverFetch('/search', {
    headers: {
      'X-BTAA-Client-Name': 'geoportal-web',
      'X-BTAA-Client-Channel': 'browser',
    },
  });
  headers = fetchMock.mock.calls[1][1].headers as Headers;
  expect(headers.get('X-API-Key')).toBe('test-only-key');
  expect(headers.get('X-BTAA-Client-Name')).toBe('geoportal-web');
  expect(headers.get('X-BTAA-Client-Channel')).toBe('browser');
});

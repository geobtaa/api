// @vitest-environment node
import { beforeEach, expect, it, vi } from 'vitest';
import { serverFetch } from '../../app/lib/server-api';
import {
  action,
  loader as loginLoader,
} from '../../app/routes/analytics.login';
import { loader } from '../../app/routes/analytics.google.callback';

vi.mock('../../app/lib/server-api', () => ({ serverFetch: vi.fn() }));
const fetchMock = vi.mocked(serverFetch);
const args = (request: Request) => ({
  request,
  params: {},
  context: {},
  url: new URL(request.url),
  pattern: '',
});
const callback = (query = `code=test-code&state=${'s'.repeat(43)}`) =>
  args(
    new Request(`https://example.org/analytics/google/callback?${query}`, {
      headers: { Cookie: 'btaa_analytics_google=browser' },
    })
  );
beforeEach(() => {
  vi.unstubAllEnvs();
  fetchMock.mockReset();
});

it('starts Google login using a same-origin POST and forwards the browser-binding cookie', async () => {
  fetchMock.mockResolvedValue(
    new Response(
      JSON.stringify({
        url: 'https://accounts.google.com/o/oauth2/v2/auth?state=test',
      }),
      { headers: { 'Set-Cookie': 'btaa_analytics_google=browser; HttpOnly' } }
    )
  );
  const response = await action(
    args(
      new Request('https://example.org/analytics/login', {
        method: 'POST',
        headers: { Origin: 'https://example.org' },
        body: new URLSearchParams({ intent: 'google' }),
      })
    )
  );
  expect(response).toBeInstanceOf(Response);
  expect((response as Response).headers.get('Location')).toMatch(
    /^https:\/\/accounts.google.com\//
  );
  expect((response as Response).headers.get('Set-Cookie')).toContain(
    'HttpOnly'
  );
  expect(fetchMock.mock.calls[0][0]).toBe('/analytics/auth/google/start');
});
it('sets both callback cookies and uses the configured HTTPS origin behind a proxy', async () => {
  vi.stubEnv('APPLICATION_URL', 'https://example.org');
  const headers = new Headers();
  headers.append('Set-Cookie', 'btaa_analytics_session=session; HttpOnly');
  headers.append('Set-Cookie', 'btaa_analytics_google=; Max-Age=0');
  fetchMock.mockResolvedValue(new Response('{}', { headers }));
  const response = await loader(callback());
  expect(response.headers.get('Location')).toBe('/analytics?welcome=1');
  expect(response.headers.getSetCookie()).toHaveLength(2);
  expect(response.headers.get('Cache-Control')).toContain('no-store');
  expect(fetchMock.mock.calls[0][1]).toMatchObject({
    method: 'POST',
    headers: {
      Origin: 'https://example.org',
      Cookie: 'btaa_analytics_google=browser',
    },
  });
});
it.each([
  ['error=access_denied', 'google-cancelled'],
  ['code=x&state=bad', 'google-failed'],
])(
  'handles invalid callback %s without exchanging a code',
  async (query, error) => {
    const response = await loader(callback(query));
    expect(response.headers.get('Location')).toBe(
      '/analytics/login?error=' + error
    );
    expect(fetchMock).not.toHaveBeenCalled();
  }
);
it.each([
  [403, 'google-denied'],
  [400, 'google-failed'],
  [503, 'google-failed'],
])(
  'handles provider failure %s without reflecting provider details',
  async (status, error) => {
    fetchMock.mockResolvedValue(new Response('sensitive details', { status }));
    const response = await loader(callback());
    expect(response.headers.get('Location')).toBe(
      '/analytics/login?error=' + error
    );
    expect(response.headers.get('Set-Cookie')).toBeNull();
  }
);
it('returns a useful login error when the API is unavailable', async () => {
  fetchMock.mockRejectedValue(new Error('unavailable'));
  const response = await loginLoader(
    args(new Request('https://example.org/analytics/login'))
  );
  expect(response.data.unavailable).toBe(true);
  expect(response.data.error).toContain('temporarily unavailable');
});

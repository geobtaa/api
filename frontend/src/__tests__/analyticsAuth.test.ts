// @vitest-environment node
import manifest from '../../private-analytics-reports/manifest.json';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { serverFetch } from '../../app/lib/server-api';
import {
  requireAnalyticsSession,
  safeNext,
} from '../../app/lib/analytics-auth.server';
import { loader as reportLoader } from '../../app/routes/analytics';
import { loader as downloadLoader } from '../../app/routes/analytics.download';
import { action } from '../../app/routes/analytics.login';

vi.mock('../../app/lib/server-api', () => ({ serverFetch: vi.fn() }));
const fetchMock = vi.mocked(serverFetch);
const request = (path = '/analytics') =>
  new Request('https://example.org' + path, {
    headers: { Cookie: 'btaa_analytics_session=test' },
  });
const args = (path: string, params = {}) => ({
  request: request(path),
  params,
  context: {},
  url: new URL('https://example.org/analytics'),
  pattern: '/analytics',
});
beforeEach(() => {
  fetchMock.mockReset();
  vi.unstubAllEnvs();
});

describe('analytics access boundaries', () => {
  it('protects report HTML/data and archive downloads before returning anything', async () => {
    fetchMock.mockImplementation(async () => new Response('', { status: 401 }));
    for (const run of [
      () => reportLoader(args('/analytics/content')),
      () =>
        downloadLoader(
          args('/analytics-reports/manifest.json', { '*': 'manifest.json' })
        ),
    ]) {
      try {
        await run();
        throw new Error('Expected redirect');
      } catch (error) {
        expect(error).toBeInstanceOf(Response);
        const response = error as Response;
        expect(response.status).toBe(302);
        expect(response.headers.get('Location')).toMatch(/^\/analytics\/login/);
        expect(response.headers.get('Cache-Control')).toBe('private, no-store');
      }
    }
  });
  it('fails closed if the auth service is unavailable', async () => {
    fetchMock.mockImplementation(() => {
      throw new Error('offline');
    });
    let failure: unknown;
    try {
      await requireAnalyticsSession(request());
    } catch (error) {
      failure = error;
    }
    expect(failure).toBeInstanceOf(Response);
    expect((failure as Response).status).toBe(503);
  });
  it('forwards session cookies and returns authenticated snapshot data without caching', async () => {
    fetchMock.mockResolvedValue(Response.json({ authenticated: true }));
    const result = await reportLoader(args('/analytics'));
    expect(fetchMock).toHaveBeenCalledWith(
      '/analytics/auth/session',
      expect.objectContaining({
        headers: { Cookie: 'btaa_analytics_session=test' },
        cache: 'no-store',
      })
    );
    expect(result).toHaveProperty('data.snapshot');
  });
  it('rejects archive traversal even with a valid session', async () => {
    fetchMock.mockImplementation(async () =>
      Response.json({ authenticated: true })
    );
    await expect(
      downloadLoader(
        args('/analytics-reports/private', { '*': '../package.json' })
      )
    ).rejects.toMatchObject({ status: 404 });
  });
  it('serves private archives only after authentication, with no-store headers', async () => {
    fetchMock.mockResolvedValue(Response.json({ authenticated: true }));
    const response = await downloadLoader(
      args('/analytics-reports/manifest.json', { '*': 'manifest.json' })
    );
    expect(response.headers.get('Cache-Control')).toBe('private, no-store');
    expect(response.headers.get('Content-Disposition')).toContain('attachment');
    expect(await response.json()).toHaveProperty('periods');
  });
  it('protects evidence downloads and serves the exact authenticated packet', async () => {
    const entry = manifest.periods[0];
    const resource = `${entry.id}/${entry.revision}/evidence-${entry.evidence.checksum}.json`;
    fetchMock.mockResolvedValue(new Response('', { status: 401 }));
    await expect(
      downloadLoader(args(`/analytics-reports/${resource}`, { '*': resource }))
    ).rejects.toMatchObject({ status: 302 });
    fetchMock.mockImplementation(async () =>
      Response.json({ authenticated: true })
    );
    const response = await downloadLoader(
      args(`/analytics-reports/${resource}`, { '*': resource })
    );
    expect(response.headers.get('Cache-Control')).toBe('private, no-store');
    expect(await response.json()).toMatchObject({
      reportRevision: entry.revision,
      evidenceChecksum: entry.evidence.checksum,
    });
    await expect(
      downloadLoader(
        args('/analytics-reports/private', {
          '*': `${entry.id}/${entry.revision}/receipts.json`,
        })
      )
    ).rejects.toMatchObject({ status: 404 });
  });
  it('does not accept open redirects', () => {
    for (const path of [
      'https://evil.example',
      '//evil.example',
      '/analytics/../../secret',
      '/analytics/\\evil.example',
      '/analytics/login',
    ])
      expect(safeNext(path)).toBe('/analytics');
    expect(safeNext('/analytics/content?month=2026-09')).toBe(
      '/analytics/content?month=2026-09'
    );
  });
  it('rejects cross-origin sign-in before contacting the API', async () => {
    const post = new Request('https://example.org/analytics/login', {
      method: 'POST',
      headers: { Origin: 'https://evil.example' },
      body: new URLSearchParams({
        intent: 'password',
        password: 'test-password',
      }),
    });
    await expect(
      action({
        request: post,
        params: {},
        context: {},
        url: new URL('https://example.org/analytics'),
        pattern: '/analytics',
      })
    ).rejects.toMatchObject({ status: 403 });
    expect(fetchMock).not.toHaveBeenCalled();
  });
  it('forwards a successful session cookie and redirects only within analytics', async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        { authenticated: true },
        {
          headers: {
            'Set-Cookie':
              'btaa_analytics_session=secret; HttpOnly; Secure; SameSite=Lax; Path=/',
          },
        }
      )
    );
    const post = new Request(
      'https://example.org/analytics/login?next=https://evil.example',
      {
        method: 'POST',
        headers: { Origin: 'https://example.org' },
        body: new URLSearchParams({
          intent: 'password',
          password: 'test-password',
        }),
      }
    );
    const response = (await action({
      request: post,
      params: {},
      context: {},
      url: new URL('https://example.org/analytics'),
      pattern: '/analytics',
    })) as Response;
    expect(response.headers.get('Location')).toBe('/analytics?welcome=1');
    expect(response.headers.get('Set-Cookie')).toContain('HttpOnly');
    expect(response.headers.get('Cache-Control')).toBe('private, no-store');
  });
  it('logs out with the session cookie and forwards its deletion before redirecting', async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        { authenticated: false },
        {
          headers: {
            'Set-Cookie':
              'btaa_analytics_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax',
          },
        }
      )
    );
    const post = new Request('https://example.org/analytics/login', {
      method: 'POST',
      headers: {
        Origin: 'https://example.org',
        Cookie: 'btaa_analytics_session=existing',
      },
      body: new URLSearchParams({ intent: 'logout' }),
    });
    const response = (await action({
      request: post,
      params: {},
      context: {},
      url: new URL(post.url),
      pattern: '/analytics/login',
    })) as Response;
    expect(response.headers.get('Location')).toBe('/analytics/login');
    expect(response.headers.get('Set-Cookie')).toContain('Max-Age=0');
    expect(fetchMock.mock.calls[0][0]).toContain('/analytics/auth/logout');
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).get('Cookie')).toBe(
      'btaa_analytics_session=existing'
    );
  });
  it('uses the configured public origin behind the reverse proxy', async () => {
    vi.stubEnv('APPLICATION_URL', 'https://example.org');
    fetchMock.mockResolvedValue(Response.json({ authenticated: true }));
    const post = new Request('http://internal:3000/analytics/login', {
      method: 'POST',
      headers: { Origin: 'https://example.org' },
      body: new URLSearchParams({
        intent: 'password',
        password: 'test-password',
      }),
    });
    const response = (await action({
      request: post,
      params: {},
      context: {},
      url: new URL(post.url),
      pattern: '/analytics/login',
    })) as Response;
    expect(response.status).toBe(302);
  });
});

it.each([401, 429, 503])(
  'handles password failure %s without returning the password',
  async (status) => {
    fetchMock.mockResolvedValue(
      new Response('private provider details', { status })
    );
    const post = new Request('https://example.org/analytics/login', {
      method: 'POST',
      headers: { Origin: 'https://example.org' },
      body: new URLSearchParams({
        intent: 'password',
        password: 'sensitive-test-password',
      }),
    });
    const result = await action({ ...args('/analytics/login'), request: post });
    expect(result).toHaveProperty('data.error');
    expect(JSON.stringify(result)).not.toContain('sensitive-test-password');
    expect(JSON.stringify(result)).not.toContain('private provider details');
    expect(fetchMock.mock.calls[0][0]).toBe('/analytics/auth/password');
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      password: 'sensitive-test-password',
    });
  }
);

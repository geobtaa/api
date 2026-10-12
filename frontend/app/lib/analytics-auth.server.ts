import { redirect } from 'react-router';
import { serverFetch } from './server-api';

export const analyticsHeaders = {
  'Cache-Control': 'private, no-store',
  'Referrer-Policy': 'no-referrer',
  'X-Robots-Tag': 'noindex, nofollow',
};

export async function requireAnalyticsSession(request: Request) {
  let response: Response;
  try {
    response = await serverFetch('/analytics/auth/session', {
      headers: { Cookie: request.headers.get('cookie') ?? '' },
      cache: 'no-store',
    });
  } catch {
    throw new Response('Analytics sign-in is temporarily unavailable', {
      status: 503,
      headers: analyticsHeaders,
    });
  }
  if (response.status === 401) {
    const url = new URL(request.url);
    throw redirect(
      `/analytics/login?next=${encodeURIComponent(url.pathname + url.search)}`,
      {
        headers: analyticsHeaders,
      }
    );
  }
  if (!response.ok)
    throw new Response('Analytics sign-in is temporarily unavailable', {
      status: 503,
      headers: analyticsHeaders,
    });
  return response.json() as Promise<{ email: string }>;
}

export function safeNext(value: string | null) {
  if (!value || !/^\/analytics(?:\/|\?|$)/.test(value)) return '/analytics';
  const url = new URL(value, 'https://local.invalid');
  if (
    value.includes('\\') ||
    url.origin !== 'https://local.invalid' ||
    !/^\/analytics(?:\/|$)/.test(url.pathname) ||
    url.pathname === '/analytics/login'
  )
    return '/analytics';
  return url.pathname + url.search;
}

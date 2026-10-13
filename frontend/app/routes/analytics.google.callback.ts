import { redirect, type LoaderFunctionArgs } from 'react-router';
import { serverFetch } from '../lib/server-api';
import { analyticsHeaders } from '../lib/analytics-auth.server';

export const headers = () => analyticsHeaders;

export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const headers = new Headers(analyticsHeaders);
  const fail = (reason: string) =>
    redirect(`/analytics/login?error=${reason}`, { headers });
  if (url.searchParams.has('error')) return fail('google-cancelled');
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  if (
    !code ||
    code.length > 4096 ||
    !state ||
    !/^[A-Za-z0-9_-]{43}$/.test(state)
  )
    return fail('google-failed');
  try {
    const response = await serverFetch('/analytics/auth/google/callback', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Google redirects here without an Origin header. The backend verifies
        // the single-use state and its HttpOnly browser-binding cookie.
        Origin: new URL(
          process.env.ANALYTICS_BASE_URL ||
            process.env.APPLICATION_URL ||
            request.url
        ).origin,
        Cookie: request.headers.get('cookie') ?? '',
      },
      body: JSON.stringify({ code, state }),
    });
    if (!response.ok)
      return fail(response.status === 403 ? 'google-denied' : 'google-failed');
    for (const cookie of response.headers.getSetCookie())
      headers.append('Set-Cookie', cookie);
    return redirect('/analytics?welcome=1', { headers });
  } catch {
    return fail('google-failed');
  }
}

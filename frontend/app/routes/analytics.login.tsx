/* eslint-disable react-refresh/only-export-components */
import {
  ArrowRight,
  LockKeyhole,
  AlertCircle,
  ExternalLink,
} from 'lucide-react';
import { AnalyticsHeader } from '../../src/components/analytics/AnalyticsHeader';
import { primaryCtaClass } from '../../src/styles/cta';
import '../../src/styles/analytics.css';
import '../../src/styles/analytics-login.css';
import {
  Form,
  data,
  redirect,
  useActionData,
  useNavigation,
  type ActionFunctionArgs,
} from 'react-router';
import { serverFetch } from '../lib/server-api';
import { analyticsHeaders } from '../lib/analytics-auth.server';

export const headers = () => analyticsHeaders;
export const meta = () => [
  { title: 'Sign in — BTAA Analytics' },
  { name: 'robots', content: 'noindex, nofollow' },
];
export function loader() {
  return data(null, { headers: analyticsHeaders });
}
export async function action({ request }: ActionFunctionArgs) {
  if (
    request.headers.get('origin') !==
    new URL(
      process.env.ANALYTICS_BASE_URL ||
        process.env.APPLICATION_URL ||
        request.url
    ).origin
  )
    throw new Response('Invalid request origin', {
      status: 403,
      headers: analyticsHeaders,
    });
  const form = await request.formData();
  const intent = form.get('intent');
  if (intent !== 'password' && intent !== 'logout')
    throw new Response('Invalid action', {
      status: 400,
      headers: analyticsHeaders,
    });
  let response: Response;
  try {
    response = await serverFetch(`/analytics/auth/${intent}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Origin: request.headers.get('origin')!,
        Cookie: request.headers.get('cookie') ?? '',
      },
      body: JSON.stringify(
        intent === 'password' ? { password: form.get('password') } : {}
      ),
    });
  } catch {
    return data(
      { error: 'Sign-in is temporarily unavailable. Please try again.' },
      { status: 503, headers: analyticsHeaders }
    );
  }
  if (!response.ok) {
    const error =
      response.status === 401
        ? 'That password isn’t correct. Please try again.'
        : response.status === 429
          ? 'Too many sign-in attempts. Please try again in 15 minutes.'
          : response.status === 422
            ? 'Enter the analytics password.'
            : 'Sign-in is temporarily unavailable. Please try again.';
    // Never return the submitted password or backend error details to the page.
    return data(
      { error },
      { status: response.status, headers: analyticsHeaders }
    );
  }
  const headers = new Headers(analyticsHeaders);
  const cookie = response.headers.get('set-cookie');
  if (cookie) headers.set('Set-Cookie', cookie);
  return redirect(
    intent === 'logout' ? '/analytics/login' : '/analytics?welcome=1',
    { headers }
  );
}

export default function AnalyticsLogin() {
  const result = useActionData<typeof action>();
  const busy = useNavigation().state !== 'idle';
  return (
    <div className="analytics-page analytics-login flex min-h-screen flex-col bg-gray-50">
      <AnalyticsHeader />
      <main id="analytics-main" tabIndex={-1} className="flex-1">
        <div className="border-b border-gray-200 bg-white px-4 py-8 sm:px-6 lg:px-8">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-500">
            Geospatial Information Network
          </p>
          <h1 className="text-3xl font-semibold leading-tight text-gray-900">
            Sign in to analytics
          </h1>
          <p className="mt-3 max-w-2xl text-base leading-6 text-gray-600">
            Explore how people discover and use the Big Ten Academic Alliance’s
            geospatial resources.
          </p>
        </div>
        <div className="grid max-w-5xl gap-8 px-4 py-10 sm:px-6 lg:grid-cols-5 lg:gap-10 lg:px-8">
          <section
            aria-labelledby="analytics-login-heading"
            className="rounded-lg border border-gray-200 bg-white p-6 lg:col-span-3"
          >
            <h2
              id="analytics-login-heading"
              className="text-xl font-semibold text-gray-900"
            >
              Enter the analytics password
            </h2>
            <p
              id="analytics-password-help"
              className="mb-6 mt-2 text-sm leading-6 text-gray-600"
            >
              Use the password shared with you by the project team.
            </p>
            {result?.error && (
              <div
                role="alert"
                className="mb-6 flex items-start gap-3 rounded-md border border-red-200 bg-red-50 p-4 text-sm leading-6 text-red-700"
              >
                <AlertCircle
                  aria-hidden="true"
                  className="mt-1 h-4 w-4 shrink-0"
                />
                <p>{result.error}</p>
              </div>
            )}
            <Form method="post" aria-busy={busy}>
              <input type="hidden" name="intent" value="password" />
              <label
                htmlFor="analytics-password"
                className="block text-sm font-medium text-gray-900"
              >
                Password
              </label>
              <input
                id="analytics-password"
                name="password"
                type="password"
                required
                autoComplete="current-password"
                maxLength={1024}
                aria-describedby="analytics-password-help"
                className="mb-5 mt-2 w-full rounded-md border border-gray-300 bg-white px-3 py-3 text-base text-gray-900 focus:border-brand-active focus:outline-none focus:ring-2 focus:ring-brand-active"
              />
              <button
                disabled={busy}
                className={`${primaryCtaClass} min-h-11 justify-center disabled:cursor-wait disabled:opacity-60`}
              >
                <LockKeyhole aria-hidden="true" className="h-4 w-4" />
                {busy ? 'Signing in…' : 'Sign in'}
              </button>
            </Form>
            <p className="mt-5 text-sm leading-6 text-gray-500">
              Your access lasts for 24 hours. Sign out when you’re finished on a
              shared computer.
            </p>
          </section>
          <aside
            aria-labelledby="analytics-access-heading"
            className="py-2 lg:col-span-2"
          >
            <h2
              id="analytics-access-heading"
              className="text-xl font-semibold text-gray-900"
            >
              Access to the reports
            </h2>
            <p className="mt-3 text-sm leading-6 text-gray-600">
              Analytics are available to members and collaborators of the
              Geospatial Information Network. Please keep the shared password
              within your review group.
            </p>
            <p className="mt-4 text-sm leading-6 text-gray-600">
              Need the password or help signing in?{' '}
              <a
                href="/feedback"
                className="font-medium text-brand-active underline underline-offset-4 hover:text-brand focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand-active"
              >
                Contact the project team
              </a>
              .
            </p>
            <div className="mt-6 border-t border-gray-200 pt-5">
              <a
                href="/"
                className="inline-flex items-center gap-2 text-sm font-medium text-brand-active hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand-active"
              >
                Explore the Geoportal{' '}
                <ArrowRight aria-hidden="true" className="h-4 w-4" />
              </a>
            </div>
          </aside>
        </div>
      </main>
      <footer className="bg-brand px-4 py-8 text-white sm:px-6 lg:px-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <a
            href="https://gin.btaa.org/"
            className="w-fit rounded-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
          >
            <img
              src="/gin-white.png"
              alt="Big Ten Academic Alliance Geospatial Information Network"
              width="580"
              height="160"
              className="h-auto w-64 max-w-full"
            />
          </a>
          <a
            href="https://gin.btaa.org/"
            className="inline-flex w-fit items-center gap-2 text-sm text-white hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white"
          >
            About the network{' '}
            <ExternalLink aria-hidden="true" className="h-4 w-4" />
          </a>
        </div>
      </footer>
    </div>
  );
}

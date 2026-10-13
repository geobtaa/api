/* eslint-disable react-refresh/only-export-components */
import { useEffect, useState, useRef } from 'react';
import {
  ArrowRight,
  Mail,
  CircleCheck,
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
  useLoaderData,
  type LoaderFunctionArgs,
  useNavigation,
  useSubmit,
  type ActionFunctionArgs,
} from 'react-router';
import { serverFetch } from '../lib/server-api';
import { analyticsHeaders } from '../lib/analytics-auth.server';

export const headers = () => analyticsHeaders;
export const meta = () => [
  { title: 'Sign in — BTAA Analytics' },
  { name: 'robots', content: 'noindex, nofollow' },
];
export async function loader({ request }: LoaderFunctionArgs) {
  let google = false;
  let unavailable = false;
  try {
    const response = await serverFetch('/analytics/auth/options');
    if (!response.ok) throw new Error('Unavailable');
    google = (await response.json()).google === true;
  } catch {
    unavailable = true;
  }
  const failure = new URL(request.url).searchParams.get('error');
  const error =
    failure === 'google-denied'
      ? 'This Google account does not have access. Choose your approved account or contact the project team.'
      : failure === 'google-cancelled'
        ? 'Google sign-in was cancelled. You can try again when you’re ready.'
        : failure === 'google-failed'
          ? 'Google sign-in could not be completed. Please try again.'
          : unavailable
            ? 'Sign-in is temporarily unavailable. Please try again.'
            : '';
  return data({ google, unavailable, error }, { headers: analyticsHeaders });
}
export async function action({ request }: ActionFunctionArgs) {
  // Require browser same-origin POSTs before forwarding cookies to the API.
  if (
    request.headers.get('origin') !==
    new URL(
      process.env.ANALYTICS_BASE_URL ||
        process.env.APPLICATION_URL ||
        request.url
    ).origin
  ) {
    throw new Response('Invalid request origin', {
      status: 403,
      headers: analyticsHeaders,
    });
  }
  const form = await request.formData();
  const intent = form.get('intent');
  if (!['request', 'verify', 'logout', 'google'].includes(String(intent))) {
    throw new Response('Invalid action', {
      status: 400,
      headers: analyticsHeaders,
    });
  }
  let response: Response;
  try {
    response = await serverFetch(
      `/analytics/auth/${intent === 'google' ? 'google/start' : intent}`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Origin: request.headers.get('origin')!,
          Cookie: request.headers.get('cookie') ?? '',
        },
        body: JSON.stringify(
          intent === 'request'
            ? { email: form.get('email') }
            : { token: form.get('token') }
        ),
      }
    );
  } catch {
    return data(
      {
        error: 'Sign-in is temporarily unavailable. Please try again.',
        message: '',
      },
      { status: 503, headers: analyticsHeaders }
    );
  }
  if (!response.ok) {
    const error =
      response.status === 400
        ? 'This link has expired or has already been used. Request a new link below.'
        : response.status === 429
          ? 'Too many requests. Please try again in 15 minutes.'
          : response.status === 422
            ? 'Enter a valid email address.'
            : 'Sign-in is temporarily unavailable. Please try again.';
    return data(
      { error, message: '' },
      { status: response.status, headers: analyticsHeaders }
    );
  }
  const headers = new Headers(analyticsHeaders);
  const cookie = response.headers.get('set-cookie');
  if (cookie) headers.set('Set-Cookie', cookie);
  if (intent === 'google') {
    const { url } = await response.json();
    const destination = new URL(url);
    if (destination.origin !== 'https://accounts.google.com')
      throw new Response('Invalid sign-in destination', {
        status: 502,
        headers: analyticsHeaders,
      });
    return redirect(destination.href, { headers });
  }
  if (intent === 'verify')
    return redirect('/analytics?welcome=1', {
      headers,
    });
  if (intent === 'logout') return redirect('/analytics/login', { headers });
  const delivery = await response.json();
  return data(
    {
      preview: delivery.preview,
      error: delivery.preview_error || '',
      message: delivery.preview_error
        ? ''
        : delivery.preview
          ? 'Your email is ready in the local preview. No email was sent.'
          : 'If this address is approved, a sign-in link will arrive shortly. Check your inbox and spam folder.',
    },
    { headers }
  );
}

export default function AnalyticsLogin() {
  const result = useActionData<typeof action>();
  const options = useLoaderData<typeof loader>();
  const google = options?.google ?? false;
  const error = result?.error || options?.error;
  const busy = useNavigation().state !== 'idle';
  const submit = useSubmit();
  const verifying = useRef(false);
  const emailWindow = useRef<Window | null>(null);
  const [previewUrl, setPreviewUrl] = useState('');
  useEffect(() => {
    const mail = result && 'preview' in result ? result.preview : undefined;
    if (!mail) {
      if (result) emailWindow.current?.close();
      setPreviewUrl('');
      return;
    }
    const escape = (value: string) =>
      value.replace(
        /[&<>"']/g,
        (char) =>
          ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;',
          })[char]!
      );
    const body = escape(mail.body).replace(
      /http:\/\/(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?\/analytics\/login#token=[A-Za-z0-9_-]+/g,
      (link) => `<a href="${link}" target="_self">${link}</a>`
    );
    const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="referrer" content="no-referrer"><title>Local email preview</title></head><body style="font-family:system-ui;max-width:760px;margin:48px auto;padding:24px;color:#003c5b"><h1>Local email preview</h1><p>This email was captured locally. No email was sent.</p><hr><p>To: ${escape(mail.to)}</p><h2>${escape(mail.subject)}</h2><pre style="white-space:pre-wrap;overflow-wrap:anywhere;font:inherit">${body}</pre></body></html>`;
    const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
    setPreviewUrl(url);
    if (emailWindow.current && !emailWindow.current.closed)
      emailWindow.current.location.href = url;
    return () => URL.revokeObjectURL(url);
  }, [result]);
  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const value = params.get('token');
    if (value && !verifying.current) {
      verifying.current = true;
      window.history.replaceState(
        null,
        '',
        window.location.pathname + window.location.search
      );
      void submit({ intent: 'verify', token: value }, { method: 'post' });
    }
  }, [submit]);
  const localEmail = result && 'preview' in result ? result.preview : undefined;
  const localLink = localEmail?.body.match(
    /http:\/\/(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?\/analytics\/login#token=[A-Za-z0-9_-]+/
  )?.[0];
  const confirming = verifying.current && !result?.error;
  const buttonClass = `${primaryCtaClass} min-h-11 justify-center disabled:cursor-wait disabled:opacity-60`;
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
              {confirming
                ? 'Signing you in…'
                : result?.message
                  ? 'preview' in result && result.preview
                    ? 'Your local email is ready'
                    : 'Check your inbox'
                  : google
                    ? 'Sign in with Google'
                    : 'Sign in with your email'}
            </h2>
            <p
              id="analytics-email-help"
              className="mb-6 mt-2 text-sm leading-6 text-gray-600"
            >
              {confirming
                ? 'Opening the Overview report…'
                : google
                  ? 'Choose the Google account associated with your approved email address.'
                  : 'Enter your approved email address. We’ll send you a secure sign-in link—no password needed.'}
            </p>
            {error && (
              <div
                role="alert"
                className="mb-6 flex items-start gap-3 rounded-md border border-red-200 bg-red-50 p-4 text-sm leading-6 text-red-700"
              >
                <AlertCircle
                  aria-hidden="true"
                  className="mt-1 h-4 w-4 shrink-0"
                />
                <p>{error}</p>
              </div>
            )}
            {result?.message && (
              <div
                role="status"
                className="mb-6 flex items-start gap-3 rounded-md border border-gray-200 bg-gray-50 p-4 text-sm leading-6 text-gray-700"
              >
                <CircleCheck
                  aria-hidden="true"
                  className="mt-1 h-4 w-4 shrink-0 text-brand"
                />
                <p>{result.message}</p>
              </div>
            )}
            {localEmail && localLink && (
              <section
                aria-label="Captured local email"
                className="mb-6 rounded-lg border border-blue-200 bg-blue-50 p-5"
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-brand">
                  Local email preview
                </p>
                <p className="mt-2 text-sm text-gray-700">
                  To: {localEmail.to}
                </p>
                <h3 className="mt-2 font-semibold text-brand">
                  {localEmail.subject}
                </h3>
                <p className="my-3 text-sm text-gray-700">
                  This email was captured locally. Use the link below to sign
                  in.
                </p>
                <a
                  href={localLink}
                  className={buttonClass}
                  onClick={(event) => {
                    if (
                      event.ctrlKey ||
                      event.metaKey ||
                      event.shiftKey ||
                      event.altKey
                    )
                      return;
                    event.preventDefault();
                    verifying.current = true;
                    void submit(
                      {
                        intent: 'verify',
                        token: new URLSearchParams(
                          new URL(localLink).hash.slice(1)
                        ).get('token')!,
                      },
                      { method: 'post' }
                    );
                  }}
                >
                  Sign in to Overview{' '}
                  <ArrowRight size={16} aria-hidden="true" />
                </a>
              </section>
            )}
            {previewUrl && (
              <a
                href={previewUrl}
                target="_blank"
                rel="noreferrer"
                className="mb-5 block font-medium text-brand-active underline"
              >
                Open local email preview
              </a>
            )}
            {options?.unavailable ? null : google && !confirming ? (
              <Form method="post" reloadDocument>
                <input type="hidden" name="intent" value="google" />
                <button disabled={busy} className={buttonClass}>
                  Continue with Google{' '}
                  <ArrowRight size={16} aria-hidden="true" />
                </button>
              </Form>
            ) : confirming ? (
              <p role="status">Signing in…</p>
            ) : (
              <Form
                method="post"
                onSubmit={() => {
                  verifying.current = false;
                  if (
                    ['localhost', '127.0.0.1', '[::1]'].includes(
                      window.location.hostname
                    )
                  ) {
                    emailWindow.current = window.open(
                      'about:blank',
                      'analytics-email-preview'
                    );
                  }
                }}
                aria-busy={busy}
              >
                <input type="hidden" name="intent" value="request" />
                <label
                  htmlFor="analytics-email"
                  className="block text-sm font-medium text-gray-900"
                >
                  Email address
                </label>
                <input
                  id="analytics-email"
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                  maxLength={254}
                  aria-describedby="analytics-email-help"
                  className="mb-5 mt-2 w-full rounded-md border border-gray-300 bg-white px-3 py-3 text-base text-gray-900 focus:border-brand-active focus:outline-none focus:ring-2 focus:ring-brand-active"
                />
                <button disabled={busy} className={buttonClass}>
                  <Mail aria-hidden="true" className="h-4 w-4" />
                  {busy ? 'Requesting link…' : 'Email me a sign-in link'}
                </button>
              </Form>
            )}
            <p className="mt-5 text-sm leading-6 text-gray-500">
              {google
                ? 'Your access lasts for 24 hours. Google shares your email address to confirm your access; we do not request access to your email or files.'
                : 'Sign-in links expire after 24 hours and can be used once. Your access lasts for 24 hours after signing in.'}
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
              Analytics are available to approved members and collaborators of
              the Geospatial Information Network. Use the email address
              associated with your access.
            </p>
            <p className="mt-4 text-sm leading-6 text-gray-600">
              Need access or help signing in?{' '}
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

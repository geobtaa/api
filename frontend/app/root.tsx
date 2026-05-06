import {
  Links,
  useLoaderData,
  useLocation,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from 'react-router';
import { useEffect } from 'react';
import type { LoaderFunctionArgs } from 'react-router';
import { AppErrorBoundary } from './AppErrorBoundary';
import { Providers } from './providers';
import { getThemeIdFromRequest } from './lib/theme.server';
import '../src/index.css';
import '../src/styles/leaflet.css';

const GOOGLE_TAG_MANAGER_ID = (import.meta.env.VITE_GTM_ID || '').trim();
const KAMAL_DESTINATION = (import.meta.env.VITE_KAMAL_DEST || '').trim();
const GOOGLE_TAG_MANAGER_ID_PATTERN = /^GTM-[A-Z0-9]+$/i;
const isGoogleTagManagerEnabled =
  KAMAL_DESTINATION === 'prd' &&
  GOOGLE_TAG_MANAGER_ID_PATTERN.test(GOOGLE_TAG_MANAGER_ID);

function GoogleTagManagerClient({ containerId }: { containerId: string }) {
  useEffect(() => {
    if (!containerId || document.getElementById('google-tag-manager')) return;

    const win = window as typeof window & {
      dataLayer?: Array<Record<string, unknown>>;
    };
    win.dataLayer = win.dataLayer || [];
    win.dataLayer.push({ 'gtm.start': new Date().getTime(), event: 'gtm.js' });

    const firstScript = document.getElementsByTagName('script')[0];
    const script = document.createElement('script');
    script.id = 'google-tag-manager';
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtm.js?id=${encodeURIComponent(
      containerId
    )}`;

    if (firstScript?.parentNode) {
      firstScript.parentNode.insertBefore(script, firstScript);
    } else {
      document.head.appendChild(script);
    }
  }, [containerId]);

  return null;
}

export async function loader({ request }: LoaderFunctionArgs) {
  const themeId = getThemeIdFromRequest(request);
  return { themeId };
}

export default function Root() {
  const { themeId } = useLoaderData<typeof loader>();
  const location = useLocation();
  const isMiradorRoute = location.pathname === '/mirador';
  return (
    <html lang="en" data-theme={themeId}>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="manifest" href="/manifest.webmanifest" />
        <link rel="icon" href="/favicon.ico" sizes="48x48" />
        <link rel="apple-touch-icon" href="/apple-touch-icon-180x180.png" />
        <Meta />
        <Links />
      </head>
      <body>
        {isGoogleTagManagerEnabled && !isMiradorRoute && (
          <noscript>
            <iframe
              src={`https://www.googletagmanager.com/ns.html?id=${encodeURIComponent(
                GOOGLE_TAG_MANAGER_ID
              )}`}
              height="0"
              width="0"
              style={{ display: 'none', visibility: 'hidden' }}
              title="Google Tag Manager"
            />
          </noscript>
        )}
        <AppErrorBoundary>
          {isMiradorRoute ? (
            <Outlet />
          ) : (
            <Providers initialThemeId={themeId} locationKey={location.key}>
              <Outlet />
            </Providers>
          )}
        </AppErrorBoundary>

        {/* GeoBlacklight expects a Blacklight modal container (#blacklight-modal).
            Without it, the metadata_download initializer throws and prevents all other
            GeoBlacklight initializers from running (tooltips/truncation/etc). */}
        {!isMiradorRoute && (
          <div id="blacklight-modal" className="hidden" aria-hidden="true" />
        )}

        <ScrollRestoration />
        <Scripts />
        {isGoogleTagManagerEnabled && !isMiradorRoute && (
          <GoogleTagManagerClient containerId={GOOGLE_TAG_MANAGER_ID} />
        )}
        {/* Keep this path stable so existing browsers upgrade onto the minimal
            service worker and drop the old Workbox precache safely. */}
        {!import.meta.env.DEV && <script src="/registerSW.js" />}
      </body>
    </html>
  );
}

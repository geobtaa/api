import {
  Links,
  useLoaderData,
  useLocation,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from 'react-router';
import type { ReactNode } from 'react';
import type { LoaderFunctionArgs } from 'react-router';
import { AppErrorBoundary } from './AppErrorBoundary';
import { Providers } from './providers';
import { getThemeIdFromRequest } from './lib/theme.server';
import { getDefaultThemeId, type ThemeId } from '../src/config/institution';
import { GoogleTagManager } from '../src/components/analytics/GoogleTagManager';
import { GeoportalRouteErrorBoundary } from '../src/pages/ErrorPage';
import '../src/index.css';
import '../src/styles/leaflet.css';

const GOOGLE_TAG_MANAGER_ID = (import.meta.env.VITE_GTM_ID || '').trim();
const KAMAL_DESTINATION = (import.meta.env.VITE_KAMAL_DEST || '').trim();
const GOOGLE_TAG_MANAGER_ID_PATTERN = /^GTM-[A-Z0-9]+$/i;
const isGoogleTagManagerEnabled =
  KAMAL_DESTINATION === 'prd' &&
  GOOGLE_TAG_MANAGER_ID_PATTERN.test(GOOGLE_TAG_MANAGER_ID);

export async function loader({ request }: LoaderFunctionArgs) {
  const themeId = getThemeIdFromRequest(request);
  return { themeId };
}

function RootDocument({
  children,
  isMiradorRoute = false,
  themeId,
}: {
  children: ReactNode;
  isMiradorRoute?: boolean;
  themeId: ThemeId;
}) {
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
        {children}

        {/* GeoBlacklight expects a Blacklight modal container (#blacklight-modal).
            Without it, the metadata_download initializer throws and prevents all other
            GeoBlacklight initializers from running (tooltips/truncation/etc). */}
        {!isMiradorRoute && (
          <div id="blacklight-modal" className="hidden" aria-hidden="true" />
        )}

        <ScrollRestoration />
        <Scripts />
        {/* Keep this path stable so existing browsers upgrade onto the minimal
            service worker and drop the old Workbox precache safely. */}
        {!import.meta.env.DEV && <script src="/registerSW.js" />}
      </body>
    </html>
  );
}

export default function Root() {
  const { themeId } = useLoaderData<typeof loader>();
  const location = useLocation();
  const isMiradorRoute = location.pathname === '/mirador';
  const turnstilePreview =
    import.meta.env.DEV && location.pathname === '/turnstile-preview';
  return (
    <RootDocument themeId={themeId} isMiradorRoute={isMiradorRoute}>
      <AppErrorBoundary>
        {isMiradorRoute ? (
          <Outlet />
        ) : (
          <Providers
            initialThemeId={themeId}
            locationKey={location.key}
            turnstilePreview={turnstilePreview}
          >
            {isGoogleTagManagerEnabled && (
              <GoogleTagManager
                containerId={GOOGLE_TAG_MANAGER_ID}
                locationKey={location.key}
              />
            )}
            <Outlet />
          </Providers>
        )}
      </AppErrorBoundary>
    </RootDocument>
  );
}

export function ErrorBoundary() {
  const location = useLocation();
  return (
    <RootDocument
      themeId={getDefaultThemeId()}
      isMiradorRoute={location.pathname === '/mirador'}
    >
      <GeoportalRouteErrorBoundary />
    </RootDocument>
  );
}

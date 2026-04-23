import {
  Links,
  useLoaderData,
  useLocation,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "react-router";
import type { LoaderFunctionArgs } from "react-router";
import { AppErrorBoundary } from "./AppErrorBoundary";
import { Providers } from "./providers";
import { getThemeIdFromRequest } from "./lib/theme.server";
import "../src/index.css";
import "../src/styles/leaflet.css";

export async function loader({ request }: LoaderFunctionArgs) {
  const themeId = getThemeIdFromRequest(request);
  return { themeId };
}

export default function Root() {
  const { themeId } = useLoaderData<typeof loader>();
  const location = useLocation();
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
        <AppErrorBoundary>
          <Providers initialThemeId={themeId} locationKey={location.key}>
            <Outlet />
          </Providers>
        </AppErrorBoundary>

        {/* GeoBlacklight expects a Blacklight modal container (#blacklight-modal).
            Without it, the metadata_download initializer throws and prevents all other
            GeoBlacklight initializers from running (tooltips/truncation/etc). */}
        <div id="blacklight-modal" className="hidden" aria-hidden="true" />

        <ScrollRestoration />
        <Scripts />
        {/* Keep this path stable so existing browsers upgrade onto the minimal
            service worker and drop the old Workbox precache safely. */}
        {!import.meta.env.DEV && <script src="/registerSW.js" />}
      </body>
    </html>
  );
}

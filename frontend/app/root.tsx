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

const GOOGLE_TAG_MANAGER_ID = (import.meta.env.VITE_GTM_ID || "").trim();
const KAMAL_DESTINATION = (import.meta.env.VITE_KAMAL_DEST || "").trim();
const GOOGLE_TAG_MANAGER_ID_PATTERN = /^GTM-[A-Z0-9]+$/i;
const isGoogleTagManagerEnabled =
  KAMAL_DESTINATION === "prd" &&
  GOOGLE_TAG_MANAGER_ID_PATTERN.test(GOOGLE_TAG_MANAGER_ID);

function getGoogleTagManagerScript(containerId: string) {
  return `
(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer',${JSON.stringify(containerId)});
`.trim();
}

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
        {isGoogleTagManagerEnabled && (
          <script
            dangerouslySetInnerHTML={{
              __html: getGoogleTagManagerScript(GOOGLE_TAG_MANAGER_ID),
            }}
          />
        )}
        <link rel="manifest" href="/manifest.webmanifest" />
        <link rel="icon" href="/favicon.ico" sizes="48x48" />
        <link rel="apple-touch-icon" href="/apple-touch-icon-180x180.png" />
        <Meta />
        <Links />
      </head>
      <body>
        {isGoogleTagManagerEnabled && (
          <noscript>
            <iframe
              src={`https://www.googletagmanager.com/ns.html?id=${encodeURIComponent(
                GOOGLE_TAG_MANAGER_ID
              )}`}
              height="0"
              width="0"
              style={{ display: "none", visibility: "hidden" }}
              title="Google Tag Manager"
            />
          </noscript>
        )}
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

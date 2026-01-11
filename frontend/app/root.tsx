import {
  Links,
  useLoaderData,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "react-router";
import type { LoaderFunctionArgs } from "react-router";
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
  return (
    <html lang="en" data-theme={themeId}>
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        <Providers initialThemeId={themeId}>
          <Outlet />
        </Providers>

        {/* GeoBlacklight expects a Blacklight modal container (#blacklight-modal).
            Without it, the metadata_download initializer throws and prevents all other
            GeoBlacklight initializers from running (tooltips/truncation/etc). */}
        <div id="blacklight-modal" className="hidden" aria-hidden="true" />

        <ScrollRestoration />
        <Scripts />
      </body>
    </html>
  );
}

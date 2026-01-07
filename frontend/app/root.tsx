import {
  Links,
  Meta,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "react-router";
import { Providers } from "./providers";
import "../src/index.css";
import "../src/styles/leaflet.css";

export default function Root() {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <Meta />
        <Links />
      </head>
      <body>
        <Providers>
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

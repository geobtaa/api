import React, { useEffect } from "react";
import { ApiProvider } from "../src/context/ApiContext";
import { BookmarkProvider } from "../src/context/BookmarkContext";
import { DebugProvider } from "../src/context/DebugContext";
import { MapProvider } from "../src/context/MapContext";
import { ThemeProvider } from "../src/context/ThemeContext";
import type { ThemeId } from "../src/config/institution";

/**
 * App providers + client-side boot for GeoBlacklight (Stimulus).
 *
 * We keep this intentionally simple:
 * - Start Stimulus once
 * - Import GeoBlacklight core once (it registers its own controllers/listeners)
 * - Trigger GeoBlacklight activation on initial load and on route changes
 */
export function Providers({
  children,
  initialThemeId,
  locationKey,
}: {
  children: React.ReactNode;
  initialThemeId?: ThemeId;
  locationKey?: string;
}) {
  useEffect(() => {
    // Only runs in the browser
    if (typeof window === "undefined") return;

    let cancelled = false;

    async function boot() {
      if (cancelled) return;
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const g = globalThis as any;

        // Start Stimulus once and expose it globally (GeoBlacklight expects `Stimulus`).
        if (!g.Stimulus) {
          const { Application } = await import("@hotwired/stimulus");
          g.Stimulus = Application.start();
          (window as any).Stimulus = g.Stimulus;
        }

        // Mirador is embedded via an iframe (see ResourceViewer) so we intentionally do NOT
        // register a Stimulus controller for it. This avoids any possibility of Mirador code
        // affecting the parent page.

        // Import GeoBlacklight core once; it registers its own controllers and listeners.
        if (!g.GeoblacklightCore) {
          const mod = await import(
            "@geoblacklight/frontend/app/javascript/geoblacklight/core"
          );
          g.GeoblacklightCore = (mod as any).default ?? mod;
        }

        // GeoBlacklight uses DOMContentLoaded / Turbo events; in our SSR+SPA environment,
        // those may not fire at the right time. Trigger activation on initial load + navigation.
        if (typeof g.GeoblacklightCore?.activate === "function") {
          // Some initializers assume specific DOM nodes exist and can throw if they don't.
          // Never let that take down the app or interfere with the viewer.
          // Defer one tick so the new route's DOM is committed before initializers run.
          setTimeout(() => {
            try {
              g.GeoblacklightCore.activate(new Event("react-router:navigation"));
            } catch (err) {
              // eslint-disable-next-line no-console
              console.warn("GeoBlacklight activation failed:", err);
            }
          }, 0);
        }
      } catch (err) {
        // eslint-disable-next-line no-console
        console.warn("GeoBlacklight boot failed:", err);
      }
    }

    boot().catch((err) => {
      // eslint-disable-next-line no-console
      console.warn("GeoBlacklight boot failed:", err);
    });

    return () => {
      cancelled = true;
    };
  }, [locationKey]);

  return (
    <ThemeProvider initialThemeId={initialThemeId}>
      <ApiProvider>
        <BookmarkProvider>
          <DebugProvider>
            <MapProvider>{children}</MapProvider>
          </DebugProvider>
        </BookmarkProvider>
      </ApiProvider>
    </ThemeProvider>
  );
}

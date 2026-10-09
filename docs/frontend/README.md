# Frontend Documentation

The frontend is the React/TypeScript public Geoportal interface for this
repository. It runs locally as the `frontend` Docker Compose service on host
port 5173, or directly with npm on port 3000 from `frontend/`.

## Available Documentation

Testing:

- [Testing Guide](testing.md) - test suite, coverage, accessibility checks, and
  test-writing patterns.
- [Testing Quick Reference](testing-quick-reference.md) - common testing
  commands and snippets.

Code quality:

- [Linting and Formatting](linting-and-formatting.md) - ESLint, Prettier, and
  local workflow.
- [Linting Quick Reference](linting-quick-reference.md) - short command and
  troubleshooting reference.

Features:

- [Homepage Map Visualization](homepage-map.md) - H3 hex map, featured carousel,
  preview layers, and Allmaps behavior.

Configuration:

- Deployed analytics and tag-manager configuration is restricted operations
  material. See [../analytics.md](../analytics.md) for the public stub.

## Project Overview

The frontend stack currently uses:

- React 19 and React DOM 19.
- React Router 7 for routing, loaders, SSR, build, and production serving.
- TypeScript, Vite 7, and React Router dev tooling.
- Vitest 3, Testing Library, `happy-dom`, axe, and pa11y for tests and
  accessibility checks.
- Material UI 7, Tailwind, Leaflet, GeoBlacklight frontend components, Allmaps,
  H3, Recharts, and Lucide icons.

## Unfiltered Search

The `/search` page browses the full catalog when no query or filters are present,
including URLs containing only presentation parameters such as
`/search?view=gallery&per_page=20`. Removing the last filter starts an unfiltered
search without requiring an explicit `q=` parameter. Results and facets load
through the browser search request; the map loads independently. The results
area shows a loading state until the current request settles, rather than
reporting zero results while the request is pending.

## Allmaps on resource pages

Resources with an HTTP(S) IIIF Presentation manifest or Image API reference
offer a **Georeference this map with Allmaps** link in the Map Overlay card,
even before Allmaps data has been harvested. References may be JSON strings
or objects; both HTTP and HTTPS IIIF vocabulary keys are supported. A IIIF
viewer endpoint or harvested manifest URL provides a fallback.

The Map Overlay tab embeds the official Allmaps Viewer with the complete
annotation collection. Allmaps supplies map selection, map/image views, and
viewer controls. **Open in new tab** and **Fullscreen** appear beside the
viewer tabs for both IIIF Item Viewer and Map Overlay modes. Fullscreen uses the browser API
when available, with a browser-pane expansion fallback. **Exit fullscreen**
remains available above the viewer; expanding preserves the embedded viewer state.

Mirador and Allmaps use the same 600px frame. Mirador uses a light geoportal
theme with system fonts, blue accents, and flat toolbars. Its embedded mode
(`embedded=1` on the local Mirador route) hides its internal fullscreen control
and view-layout menu while retaining thumbnails, page navigation, zoom, sidebar,
and download tools. Rotate-left and rotate-right buttons beside zoom turn the
image in 90-degree increments without resetting pan or zoom. Both embedded and
standalone Mirador use OpenSeadragon’s canvas drawer to avoid device-specific
WebGL failures (#424; workaround reported by MSU contributor @natecollins).
The standalone Mirador route retains its fullscreen control.
Switching tabs hides rather than unmounts these viewers; the Allmaps iframe is
created on its first selection. Page, region, and zoom states remain independent
and reset on resource navigation.
The iframe depends on the availability of Allmaps and the source IIIF services.

Only resources marked `allmaps_annotated` show the overlay viewer and the
external Allmaps viewer link. Those resources retain the edit-control-points
link. Link availability uses catalog metadata, without fetching external IIIF
services during page rendering; an unavailable remote service can still fail
when opened in Allmaps.

## Quick Commands

Run from `frontend/`:

```bash
# Development and production build checks
npm run dev
npm run build
npm run start

# Testing
npm test
npm run test:watch
npm run test:coverage
npm run test:a11y

# Code quality
npm run lint
npm run lint:fix
npm run format
npm run format:check
```

Run from the repository root after frontend dependency or Vite config changes:

```bash
make frontend-reset
```

Then hard-refresh the browser or use a private/incognito window to avoid stale
chunk URLs.

## Maintenance Checklist

- Update this file when `frontend/package.json` scripts or major dependencies
  change.
- Update testing docs when Vitest, Testing Library, axe, pa11y, or test setup
  changes.
- Update feature docs when homepage map, featured resource, preview-layer, or
  Allmaps behavior changes.
- Run `npm run lint`, `npm run format:check`, and `npm test` before merging
  frontend behavior changes.

PMTiles previews require Ctrl or Command plus scroll to zoom, leaving ordinary
scrolling available for the page. Unmodified scrolling briefly displays a centered
Leaflet-style instruction over a dimmed map (Command on Mac, Ctrl elsewhere); zoom buttons,
dragging, and touch interactions remain available.

Resource source links are native anchors, supporting URL previews, copy-link,
and modifier clicks. Multiple source URLs are displayed individually. Web
Services, Metadata, and Open in ArcGIS retain their selection dialogs.

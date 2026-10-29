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
- Resource-page item previews use the `ogm-viewer` web components with the
  Aardvark record already returned by the resource API. Vite leaves the
  components un-prebundled and resolves their runtime theme and icon assets in
  development, then emits those assets during production builds.

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
- Material UI 7, Tailwind, MapLibre, `ogm-viewer`, Allmaps MapLibre layers
  for homepage previews, Allmaps, H3, Recharts, and Lucide icons.

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

Eligible IIIF resource pages also check the Allmaps annotation service in the
background on each visit/reload. A valid, nonempty annotation collection reveals
the Map Overlay tab and viewer link even when harvested metadata is absent or
unannotated. Checks bypass the browser cache, time out after eight seconds, and
are cancelled on navigation. Errors or empty results preserve known harvested
overlays. Allmaps service-side caching can delay newly published annotations;
reloading retries the check. Live discovery affects this page only, not catalog
search filters or persisted harvesting status.

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

If `504 (Outdated Optimize Dep)` returns after a reset, check
`docker compose logs --tail=100 frontend` for repeated “new dependencies optimized”
messages. Dependencies loaded during route discovery belong in
`optimizeDeps.include` in `frontend/vite.config.ts` so Vite bundles them at startup
instead of invalidating dependency URLs while the page loads.

## Maintenance Checklist

- When replacing SVG artwork in `frontend/public/icons/`, add or bump its entry
  in `ICON_VERSIONS` in `frontend/src/utils/providerIcons.ts`. The homepage and
  licensed-access links use `getProviderIconUrl` to request the versioned URL,
  so browsers fetch updated artwork without clearing their existing icon cache.
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
MapLibre cooperative-gesture instruction (Command on Mac, Ctrl elsewhere); zoom buttons,
dragging, and touch interactions remain available.

Resource source links are native anchors, supporting URL previews, copy-link,
and modifier clicks. Multiple source URLs are displayed individually. Web
Services, Metadata, and Open in ArcGIS retain their selection dialogs.

### OGM Viewer basemaps

The resource viewer uses pinned `ogm-viewer` 1.6.0 with explicit OpenFreeMap Liberty
and Dark styles. Version 1.x bundles its theme and icons; the application no longer
copies viewer assets or imports private hashed asset-loader modules. Vite retains
ES module worker output for COG decoding. The standalone backend viewer pins the
same package version and basemap styles. Application geographic maps use the
shared MapLibre primitives in `frontend/src/mapping`. The resource-page Allmaps
viewer remains the official embedded viewer; specialist IIIF viewers are retained.
They preserve the existing latitude/longitude and legacy 256-pixel zoom contracts
at the application boundary, converting once to MapLibre longitude/latitude and
512-pixel zoom. GeoJSON collections share a source and use feature state for hover.
Homepage protocol previews use OGM Viewer previewers and Allmaps MapLibre layers.

The frontend Docker image and the combined application image use Node 22 and installs the committed lockfile with
`npm ci --legacy-peer-deps`, matching the MapLibre dependency runtime requirements. Both copy the OGM patch
installer and vendor files before dependency installation, including production
dependencies, so postinstall applies the same viewer changes in each image.

Search map controls:

- The Location filter, results, and resource Location maps start with compact attribution collapsed behind the native MapLibre information button. Users can open or close it with mouse or keyboard. The shared `collapsedAttribution` map option applies only the initial state; attribution remains available and later user choices are preserved.

Resource pages hide OGM Viewer's internal menubar and repeated title, so the
canvas starts directly below the page-level viewer controls.

The resource page omits OGM Viewer's metadata-only Location preview because the
sidebar already shows that map. Records without a supported content reference
skip the viewer and its controls entirely. Image, manifest, and actual map-layer
previews remain available; WMS/WMTS references require a layer identifier.

For records with both IIIF references, the viewer opens the manifest's **Images**
tab before the **Single image** tab. Failed inactive image previews become
unavailable; **Single image** tabs are hidden from the first render while the manifest
loads and after it succeeds. They are revealed if its initial load fails. A lone
preview displays its canvas without a tab bar, including during initial loading. An initial preview failure switches to another IIIF image preview
only after it has loaded; later page failures keep the reader in the book.

IIIF image downloads use the active image service already loaded by OGM Viewer.
The resource page does not make a separate manifest-derived download request,
so collections that the viewer can open do not show a second resolver's error.
Links respect the service's Image API version, advertised sizes and limits.
Paging and preview-tab changes update individual image downloads. The Downloads
page/sheet picker navigates the viewer too; publisher-provided downloads remain
available. The download heading only appears when image links are available.
The independent API endpoint remains available to other clients; see
[IIIF downloads](../backend/iiif_downloads.md) for its supported manifest shapes
and endpoint fields.

### Standalone OGM Viewer

“Open in new tab” opens `/ogm-viewer?resource=<encoded resource ID>` with
the complete catalog record and a viewport-height OGM Viewer. Its native
menubar remains available in this standalone view. The resource-page viewer
continues to omit the repeated title. Both omit the Location preview.

Existing `/mirador?manifest=<encoded manifest URL>` links permanently redirect
to `/ogm-viewer` with their query string preserved. Manifest-only links create
a minimal Aardvark record in the browser viewer; the server does not fetch the
user-supplied manifest URL. Missing or invalid inputs show an accessible message.

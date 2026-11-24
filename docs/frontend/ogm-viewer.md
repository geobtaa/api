# OGM Viewer integration

The application consumes a source-built prerelease of
[geobtaa/ogm-viewer](https://github.com/geobtaa/ogm-viewer/tree/feature/viewer-integration),
based on upstream v1.7.0. The dependency key remains `ogm-viewer`; the tarball
contains `@geobtaa/ogm-viewer` version `1.7.0-btaa.1.5`. `package.json` names an
exact release asset URL and `package-lock.json` pins its integrity.
`fork-build.json` inside the installed package identifies its source commit,
upstream baseline, build Node version, and lockfile hash. No upstream PRs have
been opened for this work.

The fork retains support for comma-separated resource bounding boxes, fixing the
initial map extent for records such as `cugir-007910`. The fork includes a WMS
browser regression covering delayed capabilities loading.

UW–Madison Image API records use an encoded slash (`%2F`) in the identifier.
When the publisher's `info.json` expands that slash, the viewer keeps the
requested encoding for image tiles and Downloads links. See
[viewer issue #3](https://github.com/geobtaa/ogm-viewer/issues/3) for a live example.

Records with multiple PMTiles archives show one preview tab per archive, in metadata order. See [viewer issue #7](https://github.com/geobtaa/ogm-viewer/issues/7).

Upstream 1.7.0 adds COG index-map mosaics, FGDC-derived legends, layer ordering
controls, and improved handling of blocked requests. Our selection/navigation
contracts and embedding options remain available.

## Ownership and contracts

The fork contains separate changes for selection/navigation events, optional
embedding controls, optional manifest presentation, and browser regression tests.
The [fork maintenance guide](https://github.com/geobtaa/ogm-viewer/blob/feature/viewer-integration/FORK.md)
describes their packaging and upgrade process. These changes live in TypeScript
source; there are no application postinstall edits to compiled viewer bundles.

`ResourceViewer.tsx` is the React adapter. It listens for public `previewChange`
and `imageChange` events, caches each preview's image, rejects old-record events,
and publishes only the active image preview. The event types are imported from
`ogm-viewer/lib`, rather than copied into the application.

`imageChange` identifies the preview and record and supplies `sequence`,
`pageIndex`, and the opened `image`. Sequence indices are viewer image indices,
not IIIF canvas indices; `occurrence` distinguishes repeated image URLs.
`image: null` clears downloads during loading, page transitions, or failure.
Optional `image.service` contains already-loaded Image API capabilities.
`viewerImageDownloads.ts` derives links from those capabilities without a
second manifest request. Publisher-provided downloads remain application-owned.

The Downloads picker dispatches `imageNavigationRequest` with the selected
record/preview identity, URL, and index. Both the adapter and viewer validate
the request; the viewer's resulting events remain authoritative. Application
code does not inspect private OpenSeadragon objects or viewer shadow DOM.

The resource page opts into `external-preview-tabs` and renders the viewer's
`previewTabsChange` choices beside Fullscreen and Open in new tab. A single
preview keeps its selected tab. Map Overlay joins the same list when available.
Selecting a preview calls `selectPreviewTab`. As previews load or recover, OGM
Viewer updates the list of visible tabs and their active and disabled states.
[Viewer issue #6](https://github.com/geobtaa/ogm-viewer/issues/6) documents the
Ann Arbor example. Standalone mode uses its built-in
navigation. Both modes use `omit-location`, `prefer-manifest` and
`hide-single-tab`. The resource page also sets `hide-menubar`. The fork's defaults preserve
upstream behavior. Location-only records do not mount a viewer. Presentation
uses Stencil state and initial-render attributes rather than DOM patching.

The application fullscreen toolbar shares its expanded state with `ResourceViewer`
through React context. The viewer fills the frame below the toolbar while expanded,
and returns to its embedded height on exit. Browser tests cover map and image
canvases, native fullscreen, and the viewport fallback.

## Basemap controls

The top-right controls start with zoom and compass, then fullscreen, then the
basemap picker. View-specific tools follow. In resource previews these are
layer opacity and globe projection. Keyboard focus follows the same order.

API and MCP embeds load the browser modules at `/api/v1/viewer-assets/`.
Docker images include these modules. A local API can use the frontend’s
`npm ci --legacy-peer-deps` installation or install just the viewer from the
repository root.

```sh
python backend/scripts/install_viewer_assets.py frontend/package-lock.json frontend/node_modules/ogm-viewer/dist/components
```

OpenFreeMap Positron is the default for interactive maps and for newly rendered
location and bounding-box thumbnails. On resource map previews, the droplet
opens layer controls, including opacity. The stacked-layers button opens the
same basemap picker as the sidebar map. A selected style is remembered on this
site. Static thumbnails use the configured renderer style regardless of that
browser preference. The externally hosted Allmaps iframe controls its own basemap.

## Verification and upgrades

1. Review the fork's focused source commits against the candidate upstream release.
2. Build and run its source/component tests and local-fixture browser suite.
3. Package a new prerelease from committed source; never replace an existing asset.
4. Update the application's exact asset URL and lockfile together. Run clean `npm ci`,
   focused component tests, `npm run test:viewer:browser`, and `npm run build`.
5. Use `make frontend-reset` after dependency/config changes and hard-refresh.
   Check representative live IIIF, ArcGIS, COG, and Allmaps records before deployment.

The browser suite runs actual components in development and production builds.
It is separate from Vitest's mocked component tests; both are useful. Fixtures
are local and network-independent. Ports 4180 and 4181 must be free.

The viewer source build bundles its decoder and MapLibre workers and WASM assets.
The application no longer substitutes worker paths, WASM paths, or basemap URLs
in compiled JavaScript; it supplies basemap URLs through public component props.

When an upstream release supplies equivalent contracts, replace the dependency,
adjust the thin adapter if necessary, and retain the browser tests. Review
`hasOgmContentPreview` at each upgrade because its supported-reference list
currently mirrors the pinned viewer's capabilities.

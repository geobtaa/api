# OGM Viewer integration

The application consumes a source-built prerelease of
[geobtaa/ogm-viewer](https://github.com/geobtaa/ogm-viewer/tree/feature/viewer-integration),
based on upstream v1.7.0. The dependency key remains `ogm-viewer`; the tarball
contains `@geobtaa/ogm-viewer` version `1.7.0-btaa.1`. `package.json` names an
exact release asset URL and `package-lock.json` pins its integrity.
`fork-build.json` inside the installed package identifies its source commit,
upstream baseline, build Node version, and lockfile hash. No upstream PRs have
been opened for this work.

The fork retains support for comma-separated resource bounding boxes, fixing the
initial map extent for records such as `cugir-007910`. The fork includes a WMS
browser regression covering delayed capabilities loading.

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

Our embedding opts into `omit-location`, `prefer-manifest`, `hide-single-tab`,
and (except standalone mode) `hide-menubar`. The fork's defaults preserve
upstream behavior. Location-only records do not mount a viewer. Presentation
uses Stencil state and initial-render attributes rather than DOM patching.

The application fullscreen toolbar shares its expanded state with `ResourceViewer`
through React context. The viewer fills the frame below the toolbar while expanded,
and returns to its embedded height on exit. Browser tests cover map and image
canvases, native fullscreen, and the viewport fallback.

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

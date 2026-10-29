# OGM Viewer selection events (temporary backport)

OGM Viewer 1.6.0 exposes loading events but no public active-image or active-preview
payload. BTAA needs both: images in hidden preview tabs can finish loading, and
OpenSeadragon's sequence position need not equal a IIIF canvas position.

`active-image-events.patch` is a proposed upstream change against the
[OpenGeoMetadata/ogm-viewer v1.6.0 source](https://github.com/OpenGeoMetadata/ogm-viewer/tree/v1.6.0)
(commit `9bf7a870b6269b636f218874edcaa6d8d68e3406`). It includes source, public
TypeScript exports, documentation, and regression tests. It has not been
submitted upstream. `preview-events.js` is compiled from that patch's helper;
its MIT license is included here.

## Event contract

Both events bubble and cross shadow roots, so consumers listen on `ogm-viewer`:

- `previewChange`: `{previewId, resourceId, resourceUrl, renderer}` on initial
  selection and preview-tab changes; `null` when there are no previews.
- `imageChange`: the same identity plus `image: {url, index, count, occurrence}` after an image
  opens. `index` is zero-based in the viewer's image sequence, **not** a canvas
  index. `occurrence` distinguishes repeated uses of the same URL. `image: null` clears the current selection on loading, page transition,
  close, or failure. `sequence` lists `{url, index, occurrence}` for each URL-backed
  image, and `pageIndex` tracks the selected position even while an image loads.
  Each image preview emits independently, including hidden tabs.
- Dispatch `imageNavigationRequest` on `ogm-viewer` with the preview identity,
  `index`, and `url` from its sequence to select an image. The image component
  validates record, preview, source URL, and bounds before calling OpenSeadragon.
  A standalone `ogm-image` receives the same request on its own host. Listeners
  are removed with the image observer.

The React adapter stores each preview's latest image, publishes only the active
preview, rejects events from other records, and unregisters listeners on cleanup.
Downloads matches `resourceUrl` and the actual image URL against API metadata.
The Downloads picker uses the reported sequence and requests navigation through
this public event contract. Viewer events remain authoritative for the picker
and download links, including loading/failure states. No matches means no image links; it never guesses the first canvas.

## Initial preview and recovery

Record-derived previews prefer the IIIF manifest image viewer, labeled **Images**,
before a standalone Image API reference, labeled **Single image**. Explicit
custom previewer order is preserved. Failed inactive IIIF image tabs are disabled
with a **Preview unavailable** tooltip. **Single image** tabs are hidden from the first render while a manifest is
loading and remain hidden after it succeeds. An initial manifest failure reveals
the fallback. An active
single image switches to the working manifest. If the initial active IIIF preview fails,
the viewer switches to another IIIF image preview only after it has opened
successfully. It never abandons an already-opened book because a later page fails,
and it respects a user's choice of a map preview. Availability resets on reload
or record changes.

## Installation and removal

`npm ci --legacy-peer-deps` runs `scripts/patch-ogm-viewer-events.mjs`. It checks
version 1.6.0 and the SHA-256 of both original component chunks before adding the
hooks and copying the helper. Re-running it is idempotent. A version or artifact
change fails installation so an upgrade cannot silently break synchronization.
The Docker dependencies stage copies the installer and vendor directory before
installing. Vite includes the helper content hash in its plugin identity to
invalidate browser dependency URLs when the backport changes. After dependency changes, rebuild the frontend dependency layer and
run `make frontend-reset`, then hard-refresh the browser.

Once an upstream release includes equivalent events, remove the postinstall
script, this vendor directory, and their Docker/Compose additions; update the
adapter's imported event types and rerun the focused tests. Application code
must continue to use public DOM events, never a private OpenSeadragon instance.

## Upstream verification

Apply the patch to a v1.6.0 checkout, then run:

```sh
npm ci --ignore-scripts --legacy-peer-deps
npm run assets
npm run test:unit -- --run src/lib/preview-events.test.ts
npx tsc --noEmit
```

The focused tests cover initial image selection, forward/backward page indices,
clear/failure states, unknown tile sources, preview switching, new records, and
listener cleanup. They also cover manifest preference, unavailable tabs, fallback
load ordering, later-page failures, and preservation of map selection. Application regression tests additionally cover hidden-image
loads, multiple images on one canvas, unmatched sources, and record navigation.

### Omitting the Location fallback

Set `omit-location` on `ogm-viewer` before loading a record to exclude its
metadata-only Location preview. Real map layers are preserved. The default
viewer behavior and explicitly supplied custom previewers are unchanged.
BTAA resource pages use this option because their sidebar already shows Location,
and skip mounting the viewer when the record has no supported content references.

When only one preview is visible, its canvas is shown without a tab bar. Tab and
navigation visibility are included in the initial render, so a successful
manifest load does not briefly show extra tabs. The preview panels stay mounted
when fallback availability changes, preserving canvas state. Multiple distinct
previews retain tab navigation.

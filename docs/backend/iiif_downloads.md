# IIIF downloads

The resource page's Downloads component supports IIIF Image API references and
Presentation 2 or 3 manifests. It loads `/api/v1/resources/{id}/downloads`
separately, so remote IIIF requests do not delay the resource page or search.
The initial resource/search `meta.ui.downloads` remains a local, provisional
list; clients that need manifest-derived downloads should use the downloads
endpoint.

For a multi-part manifest, Downloads follows the image currently open in OGM
Viewer. Moving forward/backward or switching preview tabs updates the links.
The **Page or sheet** picker also moves OGM Viewer to the selected image. Its
options come from the viewer sequence, using manifest labels where available.
Links are cleared while an image opens or when a map preview is selected.
Matching uses the preview URL and image service URL, rather than page position:
one canvas can contain several images, and some canvases have no image.

Images are downloaded individually; the API does not synthesize a ZIP, PDF, or
composite atlas image. Publisher-supplied whole-item renderings and ordinary
files remain available. Canvas renderings appear with their matching image.
The component retains its manual page selector for callers without viewer events.

## Download extraction

- Image API references may be service bases, `info.json` URLs, or image request
  URLs. The downloads endpoint reads image information to determine the version
  and advertised capabilities. Query strings and encoded identifiers survive
  URL normalization.
- Presentation 2 traverses all sequences' canvases, matching OGM Viewer's ordering, `images`, and
  `resource`. Presentation 3 uses canvases, annotation pages, painting
  annotations, and image bodies. Canvas labels support strings, Presentation 2
  language values, and Presentation 3 language maps, with page-number fallbacks.
- Image services produce aspect-preserving JPEG sizes and a full-size (Image API
  1/2) or largest-available (Image API 3) link. Version 1 uses `native` quality;
  later versions use `default`. Declared dimensions and maximum size limits
  constrain generated sizes. Level 0 services get only advertised sizes plus
  the full/largest option.
- Plain image bodies without a recognized image service use their supplied URL
  and media type. Non-painting annotations and non-HTTP(S) download URLs are
  ignored. Duplicate URLs within a canvas are removed; the same image used on
  different canvases remains available for each page.

IIIF entries have `source: "iiif"`. Entries belonging to a page also include
`canvas_id` and `canvas_label`. `iiif_resource_url` identifies the originating
manifest or standalone Image API reference; `image_source` identifies the image
service (or plain image body). `image_occurrences` records repeated uses of that
source in viewer order, distinguishing a scan reused on several canvases. Canvas rendering files have no `image_source`.
These fields are supplied in addition to `label`, `url`, `type`, and `format`.
The downloads endpoint preserves direct, generated GIS, and bridge-asset files.
If a remote provider cannot be read, those existing options remain available and
`iiif_error: true` lets the component offer a retry.

## Fetching and limits

Resolution reuses the image service's cached JSON fetch and five-second upstream
timeout, running blocking work outside the async event loop. It reads the
manifest once and resolves a separately supplied Image API reference too, so both
viewer tabs have options. It does not fetch `info.json` for every page in a large atlas.
Consequently, page-image options use the capabilities and dimensions embedded
in the manifest. Provider restrictions omitted from that metadata may still
cause a download to fail.

Only embedded canvases and annotation pages are traversed. External-only canvas
or annotation-page references and IIIF Collections are not recursively fetched.
Images the viewer cannot open have no active-image downloads. Image links open the
publisher's file in a new tab; the publisher's response determines whether the
browser displays or saves it.

## Local verification

The fixtures `backend/tests/fixtures/iiif_peace_463.json` and
`backend/tests/fixtures/iiif_atlas_463.json` are reduced public CONTENTdm manifests
from the Peace map and Standard atlas of Norman County examples in
[issue #463](https://github.com/geobtaa/api/issues/463). The atlas fixture retains
pages 1, 2, and 67 to test ordering without including the entire manifest.

Run the focused backend tests without database setup:

```bash
BTAA_SKIP_TEST_DB=1 python -m pytest backend/tests/services/test_iiif_downloads.py backend/tests/services/test_download_service.py
```

From `frontend/`, run:

```bash
npm test -- --run src/__tests__/components/resource/DownloadsTable.test.tsx src/__tests__/components/resource/ResourceViewer.test.tsx src/__tests__/components/ResourceView.test.tsx
```

Reference specifications: [Image API 2](https://iiif.io/api/image/2.1/),
[Image API 3](https://iiif.io/api/image/3.0/),
[Presentation 2](https://iiif.io/api/presentation/2.1/), and the
[Presentation 3 multi-page recipe](https://iiif.io/api/cookbook/recipe/0009-book-1/).


See [the OGM Viewer source fork](../frontend/ogm-viewer.md)
for the event contract, browser checks, and upgrade/removal instructions.

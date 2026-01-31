# Homepage Map Visualization

## Overview

The homepage features an interactive Leaflet map that combines three main elements:

1. **H3 Hex Map** — Resource density visualization using Uber's H3 hexagonal grid
2. **Featured Resources Carousel** — Curated examples that showcase different resource types and previews
3. **Search Here** — Button to search within the current map extent (appears after user pan/zoom)

The map uses a Carto light basemap and is centered south of the continental US so North America appears beneath the search form. Chicago (a dense hex cluster) is positioned for visual prominence via an initial programmatic pan.

---

## H3 Hex Map (H3Geo)

### What It Is

The hex map aggregates geospatial resource counts into H3 cells and renders them as colored hexagons. Color intensity (light blue → dark blue) indicates resource density: darker hexagons have more resources in that area.

### How It Works

- **Resolution mapping**: Leaflet zoom level maps to H3 resolution (2–8). Lower zoom = coarser hexes; higher zoom = finer hexes.
- **API**: `MapUpdaterHex` uses `useMapH3`, which calls `fetchMapH3` with the viewport bbox and resolution. The backend `/api/v1/map/h3` endpoint returns hex indexes and counts.
- **Data flow**: On map move/zoom, the component sends the visible bounds to the API. Hexes are fetched, then rendered as GeoJSON polygons using `cellToBoundary` from `h3-js`.
- **Color ramp**: 10-step blue ramp; each hex color is chosen by its count relative to the max count in the current view.

### Zoom-to-Resolution

| Leaflet Zoom | H3 Resolution | Typical Use |
|--------------|---------------|-------------|
| ≤3 | 2 | Large country / multi-country |
| 4 | 3 | Country / state |
| 5–6 | 4 | State / multi-county |
| 7–8 | 5 | County |
| 9–10 | 6 | City |
| 11–12 | 7 | Town / neighborhood |
| >12 | 8 | Neighborhood / block |

See [H3 Pyramid Design](../backend/h3_pyramid_design.md) for backend indexing, exclusion rules (global/near-global resources), and scale-aware indexing.

### Hex Hover

Hovering a hex shows a popover (bottom-left) with:

- H3 index
- Resource count
- "Search this hex" link — navigates to search with an H3 filter

---

## Featured Resources Carousel

### Configuration

Featured items are defined in `frontend/src/config/featured.ts` via `FEATURED_RESOURCE_IDS`. Each ID corresponds to a resource path (`/resources/{id}`). The list can include:

- Maps (WMS, WMTS, XYZ, etc.)
- Datasets
- Web services (ArcGIS, TileJSON, etc.)
- Imagery
- **Allmaps georeferenced maps** (IIIF resources with annotations in `resource_allmaps`)

### Carousel Behavior

1. **Visibility**: The carousel (thumbnail row) is **always visible** at the bottom of the map so users can select an item immediately without waiting.
2. **Initiating the featured experience**: The full featured experience (map fly, popup card, preview layer) starts when:
   - The user **clicks** a carousel thumbnail, OR
   - **10 seconds** pass without the user panning/zooming the map.
3. **Auto-advance**: Once initiated, the carousel advances to the next item every **10 seconds**. A progress bar on the popup card shows time remaining.
4. **Timer pause**: The timer pauses when the user hovers over:
   - The carousel thumbnails
   - The featured item popup card (bottom-right)

### Featured Experience (When Initiated)

- **Map fly**: The map flies to the active item's `dcat_bbox`. Allmaps items use tighter zoom (maxZoom 12, padding 20); others use maxZoom 10, padding 60.
- **Bounds rectangle**: A blue outline and semi-transparent fill show the resource extent.
- **Preview layer**:
  - **GeoBlacklight** (WMS, WMTS, ArcGIS, XYZ, etc.): Renders the layer via GeoBlacklight Leaflet layers.
  - **Allmaps**: Uses `@allmaps/leaflet` `WarpedMapLayer` to display georeferenced IIIF maps from the Allmaps annotation URL.
- **Popup card**: Title, description, year, resource class, thumbnail, and "View resource" link.

### User Engagement

The map tracks whether the user has panned or zoomed. If they do before the 10-second timer, the featured carousel does **not** auto-start (user engagement takes precedence). Programmatic moves (initial pan, flyToBounds for featured items) are ignored. The carousel remains visible; the user can still click a thumbnail to trigger the featured experience.

---

## Preview Layer Types

### GeoBlacklight (Leaflet) Resources

Supported protocols: WMS, WMTS, ArcGIS (dynamic, feature, tiled, image), Tile JSON, Open Index Map, TMS, XYZ. The `FeaturedItemPreviewLayer` uses `meta.ui.viewer` (protocol, endpoint, geometry) and dynamically loads the appropriate GeoBlacklight layer.

### Allmaps Georeferenced Maps

Resources with entries in the `resource_allmaps` table (where `annotated = true`) and a IIIF manifest are eligible. The API returns `meta.ui.allmaps` with:

- `allmaps_annotation_url` — URL for the Allmaps annotation (or constructed from `allmaps_manifest_uri`)
- `allmaps_annotated` — Whether georeferencing exists
- `allmaps_manifest_uri` — IIIF manifest URL

The frontend creates a `WarpedMapLayer` from `@allmaps/leaflet` using the annotation URL. Allmaps uses WebGL to warp IIIF images onto their geographic position. See [Allmaps Leaflet docs](https://allmaps.org/docs/packages/leaflet/).

---

## Component Structure

| Component | Role |
|-----------|------|
| `HomePageHexMapBackground` | Root; orchestrates map, carousel, popup, and state |
| `MapUpdaterHex` | Fetches H3 hex data, renders hexagons, handles hex hover |
| `FeaturedMapController` | Flies map to active featured item's bbox |
| `FeaturedItemPreviewLayer` | Renders GeoBlacklight or Allmaps preview layer |
| `FeaturedItemBoundsLayer` | Draws bounds rectangle for active item |
| `MapPanner` | One-time initial pan (Chicago positioning) |
| `MapUserEngagementTracker` | Detects user pan/zoom for engagement logic |
| `SearchHereControl` | "Search here" button after user interaction |

---

## Adding Featured Items

1. Add the resource ID to `FEATURED_RESOURCE_IDS` in `frontend/src/config/featured.ts`.
2. For **Allmaps** items: Ensure the resource has an `resource_allmaps` record with `annotated = true` and a valid IIIF manifest. Run the Allmaps processing task if needed (see [scripts.md](../backend/scripts.md)).
3. For **GeoBlacklight** items: Ensure `meta.ui.viewer` is populated (protocol, endpoint, geometry).

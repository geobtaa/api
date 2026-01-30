# H3 Hexagonal Grid Pyramid for Map Visualization

## Overview

Resources have three geospatial attributes:

- **`locn_geometry`** — GeoJSON (full geometry)
- **`dcat_centroid`** — centroid coordinates `[lon, lat]`
- **`dcat_bbox`** — bounding box (GeoJSON or ENVELOPE)

We already compute **`bbox_diagonal_km`** from `dcat_bbox` and store **`geo_global`** from the spatial-facets pipeline. These are essential for scale-aware H3 design.

Our collections mix **city, state, county, country, hemisphere, and global** resources. Centroid-based H3 indexing alone would create misleading visualizations—e.g. a "dark blue" hexagon off Africa representing global datasets whose centroid is often `(0, 0)` or another arbitrary point. This document designs an H3 pyramid that avoids those pitfalls.

---

## Goals

1. **Hex map**: Aggregate resource counts into H3 cells for zoom-dependent map visualization.
2. **No misleading centroids**: Exclude or specially handle global (and optionally near-global) resources so they never appear as a single "hot" hex in the ocean.
3. **Scale-aware indexing**: Use centroid, bbox, or geometry in a way that matches each resource’s geographic scale.
4. **Pyramid**: Support multiple zoom levels (H3 resolutions) with consistent aggregation semantics.

---

## Challenges

| Scale | Example | Centroid useful? | Note |
|-------|---------|------------------|------|
| **Global** | World atlas | No | Centroid often (0,0), ocean, or arbitrary. **Must not** drive a single hex. |
| **Hemisphere / continental** | Pacific Rim, Americas | Often no | Centroid can lie in ocean; single hex is misleading. |
| **Country** | United States, Germany | Debatable | One hex per country; interpretable but coarse. |
| **State / region** | Minnesota, Bavaria | Yes | Single hex per region is reasonable for density maps. |
| **County** | Marion County, IN | Yes | Well-suited to centroid. |
| **City / town** | Minneapolis, small town | Yes | Centroid is meaningful. |

---

## Recommended Zoom Levels (H3 Resolutions)

Use **7 zoom levels** corresponding to H3 resolutions **2–8**:

| Level | H3 Res | Avg edge (km) | Avg area (km²) | Typical use |
|-------|--------|----------------|----------------|-------------|
| 0 | 2 | 183 | 86,800 | Large country / multi-country |
| 1 | 3 | 69 | 12,400 | Country / state |
| 2 | 4 | 26 | 1,770 | State / multi-county |
| 3 | 5 | 9.9 | 253 | County |
| 4 | 6 | 3.7 | 36 | City |
| 5 | 7 | 1.4 | 5.2 | Town / neighborhood |
| 6 | 8 | 0.53 | 0.74 | Neighborhood / block |

**Why start at res 2?** Res 0–1 (globe / continent) are less useful once we exclude global resources from the hex map. Res 2 still supports “large region” views without inviting ocean centroids.

**Why include res 8?** Res 8 (edge ~0.53 km, area ~0.74 km²) provides neighborhood-scale detail for the hex map.

---

## Exclusion Rules (Avoid “Dark Blue Hex off Africa”)

### 1. Exclude global resources from H3 pyramid

- **Rule:** If **`geo_global === true`**, do **not** assign any H3 cell for hex-map aggregation.
- **Rationale:** Global resources have no meaningful “location” for a density map. Their centroid is arbitrary; putting them in a hex would create misleading hot spots (e.g. off Africa).
- **Implementation:** Use existing `geo_global` from spatial facets. Skip H3 computation for these resources entirely.

### 2. Exclude “near-global” by bbox size (locked)

- **Rule:** If **`bbox_diagonal_km`** > **15,000 km** (even when `geo_global` is false), treat as “near-global” and **exclude** from H3.
- **Rationale:** Catches hemisphere / multi-continent bboxes whose centroid often falls in ocean or other unhelpful places.
- **Threshold:** 15,000 km (~¾ of Earth’s half-circumference). Constant: `NEAR_GLOBAL_DIAGONAL_KM = 15_000`.

### 3. Resources without usable geometry

- **Rule:** If there is no **`dcat_bbox`** (and thus no `bbox_diagonal_km`) **and** no **`dcat_centroid`**, skip H3.
- If there is **`dcat_centroid`** but no bbox, we can still use centroid for H3 **only if** we do **not** treat the resource as global (e.g. no `geo_global`). Otherwise skip.

---

## Scale-Aware Indexing Strategy

### Option A: Centroid-only (simplest)

- **Use:** `dcat_centroid` → `h3.latlng_to_cell(lat, lng, res)` for each pyramid level.
- **Exclude:** `geo_global === true` (and optionally `bbox_diagonal_km > 15_000`).
- **Pros:** Simple, one cell per resource per resolution, easy to aggregate.
- **Cons:** Large areas (state, country) collapse to one hex; centroid for “large” resources can still be odd (e.g. continent-scale).

### Option B: Centroid for “small”, skip “large” (locked)

- **Small:** `bbox_diagonal_km <= 500` km (e.g. state-sized and smaller). Use **centroid** → H3 at each level. Constant: `CENTROID_MAX_DIAGONAL_KM = 500`.
- **Large:** `bbox_diagonal_km > 500` km **and** not global. **Do not** add to H3 pyramid (or put in a separate “large-area” bucket for non-hex UI).
- **Global / near-global:** Excluded per above.
- **Rationale:** Centroid is meaningful for state/county/city/town. For “large” non-global resources (e.g. big country, multi-country), a single centroid-based hex is still misleading, so we avoid it.

### Option C: Geometry-aware (deferred; use `locn_geometry`)

- **Use:** `h3.polygon_to_cells(geom, res)` for **`locn_geometry`** when available at each resolution.
- **Counting:** Each resource contributes to **every** hex it intersects. Totals are “resource-hex incidences,” not “unique resources per hex.” Optionally use fractional weighting (e.g. by overlap area) to avoid overcounting—more complex.
- **Exclude:** Still exclude global and near-global from H3.
- **Pros:** Large areas spread across many hexes; no single ocean hex. **Cons:** More complex aggregation and potentially inflated counts unless weighted.

**Status:** Deferred. Current implementation uses **Option B** (centroid for small, skip large). When we add Option C, we will use `locn_geometry`.

---

## Pyramid Aggregation Semantics

- **Per level:** Store one H3 cell per resource per resolution (when using centroid-based strategy). Typically **parent** relationship: cell at res 7 is contained in a cell at res 6, etc.
- **Aggregation:** For a given viewport + zoom, choose the matching H3 resolution (e.g. zoom → res 2–7), then aggregate counts by H3 index. Hierarchical aggregation (e.g. roll up res 7 → 6) can use `h3.cell_to_parent`.
- **Map tiles / API:** Return hex IDs (or hex boundaries) plus counts for the requested resolution and spatial extent. Frontend renders choropleth or symbol map by hex.

---

## Data Model / Storage

### Option 1: Store H3 IDs in Elasticsearch

- Add multivalued keyword fields, e.g. `h3_res2`, `h3_res3`, … `h3_res7` (one value per resource per resolution when assigned).
- Use `terms` aggregation on `h3_res{k}` for map queries. Filter by `geo_global = false` (and optional `bbox_diagonal_km` threshold) when building H3 pyramid.
- **Reindexing:** Compute H3 during indexing (from centroid + bbox metrics); update when `dcat_centroid` or `dcat_bbox` changes.

### Option 2: Separate H3 aggregation store

- Materialize (resource_id, h3_cell, resolution) in a dedicated table or service. Query by viewport + resolution, aggregate counts, return hex geometries (e.g. from `h3.cell_to_boundary`) for rendering.
- Keeps ES documents simpler; aggregation logic lives in the H3 pipeline.

### Option 3: Elasticsearch `geohex` / H3 plugin

- If available in your ES version, use native H3/geohex support for indexing and aggregation. Design rules (exclusions, scale-aware strategy) still apply.

---

## Summary of Design Choices

| Decision | Recommendation |
|----------|----------------|
| **Zoom levels** | **7 levels** (H3 res 2–8). |
| **Exclude global** | **Yes.** `geo_global === true` → no H3 assignment. |
| **Exclude near-global** | **Yes.** `bbox_diagonal_km > 15_000` → exclude. |
| **Indexing strategy** | **Option B:** centroid for `bbox_diagonal_km <= 500` km; skip H3 for larger non-global (or treat separately). |
| **Geometry-based (Option C)** | Deferred; will use **`locn_geometry`** when implemented. |

---

## Decisions (locked)

- **Global bucket in UI:** Yes. Show "N global resources" and support filtering (discoverable, not on hex map).
- **Option C:** When we add geometry-aware indexing, use **`locn_geometry`**.

---

## Implementation Constants (reference)

```python
# H3 pyramid resolutions for map zoom levels (7 levels)
H3_PYRAMID_RESOLUTIONS = (2, 3, 4, 5, 6, 7, 8)

# Exclusions
EXCLUDE_GLOBAL_FROM_H3 = True   # geo_global === true → no H3
NEAR_GLOBAL_DIAGONAL_KM = 15_000  # also exclude if bbox_diagonal_km > this

# Scale-aware centroid use (Option B)
CENTROID_MAX_DIAGONAL_KM = 500   # use centroid only when bbox_diagonal_km <= this
```



## References

- [H3 Resolution Table](https://h3geo.org/docs/core-library/restable) (cell counts, areas, edge lengths)
- Existing **`bbox_diagonal_km`** and **`geo_global`** (see `spatial_facets.md`, `elasticsearch/index.py`, `mappings.py`)

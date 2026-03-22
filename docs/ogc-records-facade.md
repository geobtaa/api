# OGC API - Records Compatibility Facade

This document outlines the implementation approach for adding OGC API - Records compatibility to the existing BTAA Geospatial API.

## Goal
The goal of this implementation is to provide a read-only OGC API facade (`/ogc/*`) that sits alongside the existing BTAA native API (`/api/v1/*`), without breaking any internal behavior or rebuilding the core search logic.

## Architecture

We achieved modularity and separation of concerns by employing:

1. **Existing Search Engine**: We mapped all OGC endpoints to call the existing `SearchService`. We did not write duplicate Elasticsearch queries.
2. **OGC Response Projector (`app.services.ogc_projector.OGCResponseProjector`)**: This is the core isolation layer. It takes the internal BTAA/Aardvark metadata model (which remains the canonical source of truth) and maps it into standard GeoJSON and JSON Schema formats adhering to OGC specifications.
3. **OGC Routers (`app.api.ogc.endpoints`)**: These endpoints handle parsing OGC standardized query parameters (e.g. `sortby`, `bbox`) and converting them to kwargs consumed by `SearchService`.

## What Was Implemented
The following paths are fully available under the `/ogc` prefix:
- `GET /` - OGC Landing Page.
- `GET /conformance` - Conformance declaration.
- `GET /collections` and `/collections/btaa-records` - Collection declaration. 
- `GET /collections/btaa-records/queryables` - List of mapped internal search parameters in JSON-SCHEMA format.
- `GET /collections/btaa-records/sortables` - List of mapped properties that can be sorted by.
- `GET /collections/btaa-records/items` - The main OGC collection search leveraging `limit`, `page`, `sortby`, `bbox` mapping into the existing internal queries.
- `GET /collections/btaa-records/items/{recordId}` - A single OGC item response formatted as a spatial feature.

## Property Mappings
We've abstracted the internal index property names from the publicly exposed OGC properties to keep the surface area clean:
- `id` -> `id` or `layer_slug_s`
- `title` -> `dct_title_s`
- `description` -> `dct_description_sm`
- `resourceClass` -> `gbl_resourceClass_sm`
- `resourceType` -> `gbl_resourceType_sm`
- `provider` -> `schema_provider_s`
- `spatial` -> `dct_spatial_sm`
- `subject` -> `dct_subject_sm`
- `accessRights` -> `dct_accessRights_s`
- `modified` -> `gbl_mdModified_dt`
- `dateAccessioned` -> `b1g_dateAccessioned_s`
- `publicationState` -> `b1g_publication_state_s`
- `accrualMethod` -> `b1g_dct_accrualMethod_s`

## Sort Parameter Matching
The OGC parameter `sortby` takes fields comma-separated. We map standard mappings to standard backend `SearchService` sort enums seamlessly:
- `sortby=title` -> internal `title_asc`
- `sortby=-title` -> internal `title_desc`
- `sortby=modified` -> internal `year_oldest`
- `sortby=-modified` -> internal `year_newest`
- *Empty/Missing* -> `relevance`

## Deferred Items & Future Work
For the sake of keeping the first generation realistic and strictly backward-compatible, several broader OGC features are intentionally deferred:

1. **Geometry Emissions**: We intentionally leave `geometry: null` in the GeoJSON Feature properties (for Items endpoints) because the current Aardvark data structure uses geometries differently (as bbox, points, polygons inside string arrays). Emitting true geometries reliably requires parsing WKT natively, which is slated for future work.
2. **CQL2 Text/JSON Filters**: While we map the core components like `bbox` natively, the more advanced `filter`, `filter-crs`, and `filter-lang` (specifically targeting CQL2 format parsing) are deferred to later passes.
3. **Draft Facets Extension**: OGC API Records facets are currently in draft. They are ignored for now, but the internal API has solid faceting logic ready to be projected when the standards lock down. 
4. **Dates and DateTime Ranges**: OGC supports complex `datetime` ISO strings. They are listed as arguments in our endpoints but explicitly ignored from implementation in this first pass.

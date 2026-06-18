# BTAA Geospatial API Codebase Overview

This document is a high-level tour of the BTAA Geospatial API codebase for
academic technology leaders, library technology teams, and campus partners who
want to understand the architecture without reading every source file.

The short version: this repository is a modern geospatial discovery platform. It
combines a public web application, a standards-oriented API, a search index,
  durable metadata storage, generated media assets, background synchronization
  jobs, analytics, and Model Context Protocol (MCP) access into one application
  system.

## Executive Summary

The project is designed around four goals:

- **Discovery at consortium scale**: search and browse hundreds of thousands of
  geospatial resources from Big Ten Academic Alliance institutions and partner
  repositories.
- **Reuse beyond the website**: expose complete resource details through the API
  so external applications, campus tools, QGIS, MCP clients, and future agents
  can use the same data.
- **Fast public user experience**: precompute and cache expensive resource
  representations, thumbnails, static maps, resource-class icons, and complete
  API responses.
- **Operational recoverability**: store generated cache artifacts in Postgres as
  durable cache warehouses so Redis can be flushed, restarted, or rebuilt without
  redoing all expensive work from upstream systems.

At a platform level, the system is:

- **FastAPI backend** for public API, admin APIs, MCP bridge, and maintenance
  endpoints.
- **React frontend** for the public Geoportal user experience.
- **Postgres/ParadeDB** for canonical records, auxiliary tables, generated
  cache artifacts, analytics, API keys, and job state.
- **Elasticsearch** for fast discovery, facets, spatial filtering, suggestions,
  and ranking.
- **Redis** for hot response caches, generated visual asset caches, aliases,
  locks, Celery broker usage, and short-lived state.
- **Celery/cron scripts** for background ingestion, synchronization, cache
  warming, sitemap generation, analytics maintenance, and scheduled refreshes.
- **Containerized runtime** for application roles and long-running supporting
  services. Deployed-environment procedures are restricted operations material.

## Repository Map

The most important top-level directories are:

- `backend/`: FastAPI application, service classes, database models, migrations,
  scripts, Celery tasks, tests, and API code.
- `frontend/`: React application used by the public Geoportal interface.
- `docs/`: local development, architecture, testing, public API, and
  restricted-topic stub documentation.
- `mkdocs/`: public documentation site for API specifications, linked-data
  guidance, and external user-facing docs.
- `mcp/`: MCP bridge helpers for Claude Desktop and other MCP clients.
- `qgis-plugin/`: QGIS plugin source for desktop GIS users.
- `config/`: runtime and deployment configuration files. Operational rollout
  details are restricted.
- `docker-compose.yml`: local development stack.
- `Makefile`: the main developer interface for linting, testing, priming local
  caches, syncing data locally, and running safe maintenance tasks. Remote
  operations procedures are restricted.

## Backend Architecture

The backend is organized into endpoint modules, service classes, persistence
models, background tasks, and scripts.

### API Layer

The public API is organized under `backend/app/api/v1/endpoint_modules/`.

Major endpoint groups include:

- `search.py`: search, facets, suggest, GET and POST search variants.
- `resources/`: resource detail pages and resource-specific sub-endpoints such
  as downloads, distributions, links, metadata, thumbnails, static maps,
  citations, relationships, viewer details, and similar items.
- `static_maps.py` and `thumbnails.py`: immutable visual asset serving routes.
- `gazetteer.py`: gazetteer search and lookup endpoints.
- `map.py`: H3 map aggregation endpoint.
- `mcp.py`: Model Context Protocol API bridge.
- `admin.py`: operational, sync, indexing, API-key, and cache management tools.
- `analytics.py`: public usage-event collection.
- `home.py`: homepage content APIs.
- `shapefiles.py`: shapefile query and preview support.

Endpoint modules keep request handling thin where possible. Most reusable logic
lives in service classes.

### Service Layer

The service layer lives in `backend/app/services/`. These classes and helper
modules are the heart of the application.

Core resource and presentation services:

- `search_service.py`: orchestrates Elasticsearch search, filters, facets,
  suggestions, and initial result shaping.
- `resource_representation_cache.py`: stores and retrieves generated JSON:API
  resource objects used by both `/resources/{id}` and `/search`.
- `citation_service.py` and `citation_formats_service.py`: generate APA, MLA,
  Chicago, RIS, BibTeX, and related citation formats.
- `viewer_service.py`: determines map/viewer attributes and protocols.
- `download_service.py`: builds download options, including bridge-synced asset
  downloads.
- `link_service.py`: exposes UI and API links derived from distribution data.
- `relationship_service.py`: resolves parent, collection, source, relation, and
  member relationships.
- `similar_items_service.py`: retrieves related or similar resources.
- `allmaps_service.py`: enriches records with Allmaps/IIIF annotation metadata.
- `ogm_field_mapper.py`: maps internal database fields into OGM Aardvark and B1G
  metadata namespaces.

Distribution and metadata services:

- `distribution_repository.py`: canonical access to normalized distribution
  rows and legacy `dct_references_s` reconstruction.
- `distribution_sync.py`: keeps distribution-related tables aligned with bridge
  data.
- `reference_reconstruction.py`: rebuilds reference payloads for compatibility.
- `data_dictionary_repository.py`: loads resource data dictionaries and their
  entries.
- `metadata_transform_service.py`: transforms metadata formats.

Caching and generated asset services:

- `cache_service.py`: endpoint response cache, cache keying, stale-while-
  revalidate behavior, Redis locks, tags, HTTP cache headers, ETags, and durable
  L2 response integration.
- `durable_response_cache.py`: Postgres-backed storage for generated API
  response cache records.
- `visual_asset_cache.py`: Postgres-backed storage for generated thumbnail,
  static-map, and icon bytes plus resource-to-asset links.
- `image_service.py`: thumbnail source discovery, IIIF handling, remote image
  caching, PMTiles/COG thumbnail hooks, and immutable thumbnail URLs.
- `static_map_service.py`: static map generation, basemaps, resource geometry
  maps, resource-class icons, asset aliases, and durable visual asset links.
- `thumbnail_alias_service.py`: fast resource-id to thumbnail-hash redirects.
- `thumbnail_state_service.py`: records thumbnail success, failure, placeholder,
  and source state.
- `thumbnail_queue_service.py`: prevents too many concurrent thumbnail jobs.

Data, sync, and background services:

- `bridge_sync/`: bridge API synchronization, cache refresh, search-index
  updates, and reporting around changed resources.
- `ogm_harvest/`: OpenGeoMetadata repository harvesting workflow.
- `gin_blog_service.py`: syncs public update/blog content.
- `sitemap_service.py`: generates sitemap data for crawlers.
- `spatial_facet_service.py` and `spatial_facet_indexing_service.py`: spatial
  facets and index preparation.
- `gazetteer_service.py`: gazetteer lookup and search support.
- `shapefile_service.py`: shapefile access and previews.

Access, analytics, and governance services:

- `api_key_service.py`: API key lifecycle and validation.
- `rate_limit_service.py`: API key and tier-aware rate limiting.
- `api_usage_log_service.py`: usage logging for analytics and service tiers.
- `admin_service.py`: administrative operations and orchestration.

AI and external integration services:

- `llm_service.py` and `services/llm/`: AI-assisted enrichment capabilities.
- `mcp_service.py`: exposes search and resource retrieval to MCP clients.
- `provider_throttle.py`: protects upstream providers from excessive request
  pressure.

## Data Model and Metadata Strategy

The platform stores canonical resource metadata in Postgres and indexes search
documents into Elasticsearch.

The API response model follows JSON:API and separates metadata into:

- **OGM/Aardvark fields**: interoperable geospatial discovery metadata.
- **B1G fields**: consortium-specific administrative and enrichment data.
- **UI metadata**: presentation-ready fields such as thumbnails, static maps,
  viewer configuration, downloads, citations, relationships, and similar items.

This separation is strategically important. It lets the API remain useful to:

- humans using the website,
- institutions integrating records into local discovery tools,
- GIS users through QGIS,
- external developers and data pipelines,
- AI and MCP clients that need structured resource details.

The system intentionally keeps full resource details available in both singular
and plural contexts:

- `/api/v1/resources/{id}` returns a complete resource representation.
- `/api/v1/search` returns search results with the same reusable resource
  representation shape.

That design means expensive resource enrichment work can be done once, cached,
and reused across pages, tools, and clients.

## Search Architecture

Search uses Elasticsearch as the discovery engine.

Elasticsearch handles:

- keyword search,
- faceted discovery,
- sorting,
- spatial filtering,
- H3 map aggregation support,
- suggestions/autocomplete,
- result ranking and scoring metadata.

The API then combines Elasticsearch hits with cached JSON:API resource
representations. On a warm resource cache, search result assembly avoids most
per-resource database and service calls.

The important performance distinction is:

- **Exact repeated search response**: served directly from Redis endpoint cache.
- **New search query with cached resources**: Elasticsearch still runs, but
  resource assembly is mostly cache reads.
- **Cold search query with cold resources**: Elasticsearch runs, missing resource
  representations are built, stored in Redis, and persisted in Postgres for
  future reuse.

## Caching Strategy

The caching strategy is layered. Redis is the hot path; Postgres is the durable
cache warehouse; source systems are avoided during public request handling
whenever possible.

### Principles

The system follows these caching principles:

- **Precompute expensive representations** rather than rebuilding them for every
  user.
- **Use Redis for low-latency hot reads**.
- **Use Postgres for durable generated artifacts** so Redis can be flushed or
  rebuilt safely.
- **Use immutable content-addressed asset URLs** for images and generated maps.
- **Use short alias redirects** from resource IDs to immutable asset hashes.
- **Tag cache entries by resource and namespace** so sync jobs can invalidate
  precisely.
- **Prefer stale-but-valid responses over expensive failures** during transient
  outages.
- **Bound memory growth** with TTLs, Redis maxmemory, and safe priming defaults.

### Endpoint Response Cache

`cache_service.py` wraps selected endpoints with `@cached_endpoint`.

It stores complete successful API responses as binary-safe records:

- status code,
- selected response headers,
- weak ETag,
- response body as base64,
- soft expiry,
- hard expiry,
- warm replay metadata,
- tags for invalidation.

Serving path:

1. Check Redis L1.
2. If Redis misses, check Postgres L2 in `generated_api_responses`.
3. If Postgres hits, rehydrate Redis and serve the response.
4. If both miss, compute the endpoint, store it in Redis and Postgres, and tag it.

This makes common exact API calls extremely fast while still allowing the cache
to survive Redis resets.

### Resource Representation Cache

`resource_representation_cache.py` stores the generated JSON:API resource object
used by both resource detail pages and search result pages.

This cache is crucial because resource rendering is not just one database row.
It may include:

- citations,
- downloads,
- distribution context,
- viewer metadata,
- thumbnails,
- static map URLs,
- resource-class icon URLs,
- relationships,
- Allmaps metadata,
- data dictionaries,
- OGM/B1G field mapping.

The durable table `generated_resource_representations` lets the system rebuild
Redis quickly after a Redis flush, VM recovery, or deploy.

### Visual Asset Cache

Generated visual assets include:

- remote thumbnails,
- normalized IIIF thumbnails,
- PMTiles/COG thumbnails,
- static geometry maps,
- basemap-only images,
- resource-class icons.

These are stored in two places:

- Redis DB 1 for hot image bytes.
- Postgres `generated_visual_assets` and `generated_visual_asset_links` for
  durable generated bytes and aliases.

Resource-facing URLs usually resolve through durable aliases and hot cache keys:

- `/api/v1/resources/{id}/thumbnail`
- `/api/v1/thumbnails/{resource_id}`

or:

- from `/api/v1/resources/{id}/static-map`
- to `/api/v1/static-map-assets/{map_hash}`

The hash-addressed asset URLs are immutable and can be cached aggressively by
browsers, shared caches, and future CDNs.

### Alias and Redirect Cache

For speed, the application keeps lightweight aliases from resource IDs to asset
hashes. The redirect path is intentionally small:

1. Look up resource-id alias.
2. Return `302` to immutable hash URL.
3. Let the immutable asset endpoint serve bytes.

This avoids redoing resource enrichment or loading image bodies when the browser
only needs to know where the stable asset lives.

### Cache Warming

Cache warming is done by Make targets and scripts:

- `prime-resource-cache`: builds resource representations.
- `prime-static-map-cache`: builds static-map durable assets and aliases.
- `prime-thumbnail-cache`: builds thumbnails.
- `prime-visual-caches`: runs thumbnail and static-map warmers.
- `api-response-cache-prune`: removes expired durable response rows.

Remote cache warming and pruning procedures are restricted operations material.

Static-map priming defaults are intentionally safe: full-corpus priming writes
durable assets and aliases but does not hydrate every PNG body into Redis. Small
hotsets can opt into Redis body hydration.

### Invalidation

Cache invalidation is tag-based.

Common tags include:

- `search`
- `suggest`
- `resource`
- `resource:{id}`
- `facet:{facet_name}`
- `gazetteer`
- `ns:{endpoint_namespace}`

When bridge sync changes resources, the refresh flow can:

1. collect changed resource IDs,
2. delete durable resource representations for those IDs,
3. invalidate Redis and durable API responses tagged with those resources,
4. warm generated visual assets,
5. replay known public GET paths to keep hot responses ready.

This is the operational core of keeping the API fast while still reflecting
fresh source data.

### Memory and Safety Controls

The cache design includes explicit memory safety controls:

- Redis can use memory limits and eviction policies.
- Visual asset Redis keys can use TTLs to bound hot-cache growth.
- Full-corpus static-map body hydration is blocked unless explicitly overridden.
- Durable generated artifacts live in Postgres so Redis can be reset safely.
- Expired durable API response rows are pruned by scheduled maintenance.
- Redis loading states are retried during priming to avoid false failures.
- Restricted operations runbooks cover deployed memory recovery.

Relevant runbooks:

- `docs/backend/caching.md`
- `docs/backend/vm_memory_recovery.md`
- `docs/backend/deployment.md`

## Background Jobs and Synchronization

The system maintains freshness through a mixture of admin-triggered jobs, cron
jobs, and Celery workers.

Major flows include:

- **Bridge API sync**: imports added or changed resource data from the bridge
  source, updates auxiliary tables, invalidates affected caches, warms generated
  assets, and updates the search index.
- **OpenGeoMetadata harvest**: pulls metadata from configured OGM repositories,
  imports records, and supports reindexing workflows.
- **Distribution population**: normalizes legacy `dct_references_s` into
  distribution, download, licensed access, and asset tables.
- **Search reindexing**: builds a new Elasticsearch index and atomically swaps
  aliases for safe cutover.
- **Sitemap generation**: keeps crawler-facing sitemap XML current.
- **Analytics maintenance**: rolls up usage data and manages retention.
- **Blog/homepage sync**: keeps public update content available to the frontend.

The Makefile is intentionally the shared interface for these workflows, so
developers can run consistent commands locally. Deployed command examples are
restricted operations material.

## Frontend Architecture

The frontend lives in `frontend/` and provides the public Geoportal experience.
It consumes the API rather than duplicating backend business logic.

At a high level, the frontend is responsible for:

- search and browse interactions,
- map and gallery presentation,
- resource detail pages,
- filter and facet UI,
- responsive user experience,
- consuming API-provided URLs for thumbnails, static maps, downloads, viewer
  endpoints, and citations.

The backend intentionally prepares rich JSON:API resources so the frontend can
stay focused on interaction and presentation.

## MCP and External Use

The system is built for more than the web UI.

MCP support allows AI clients and desktop tools to search and retrieve resource
information through the same API-backed service layer. The QGIS plugin gives
desktop GIS users a direct path from discovery to use.

This matters strategically because the Geoportal becomes an institutional data
platform, not only a website. The same resource details can support:

- public discovery,
- campus research tools,
- GIS workflows,
- AI assistants,
- data governance review,
- analytics and reporting,
- external API consumers.

## Deployment And Operations

Deployment, host layout, role mapping, remote cache warming, incident response,
and production maintenance procedures are restricted operations material.

Public architecture docs should describe the application shape and code
boundaries without publishing deployed topology, command sequences, hostnames,
secret handling, or capacity assumptions.

## Testing and Quality Strategy

The codebase includes tests across:

- API endpoints,
- service classes,
- cache behavior,
- static-map and thumbnail behavior,
- bridge sync,
- scripts and priming logic,
- search behavior,
- frontend components.

Backend quality gates:

- `make lint`
- `make lint-check`
- `make test-fast`
- `make test`

Frontend quality gates:

- `npm run lint`
- `npm test`
- `npm run format:check`

The practical testing philosophy is to cover service behavior and operational
edge cases, not just happy-path endpoint responses.

## Why This Architecture Matters for Academic Technology Leadership

This codebase reflects several important institutional technology values:

- **Interoperability**: OGM Aardvark, JSON:API, linked-data profiles, IIIF,
  OGC-adjacent work, QGIS integration, and MCP access all make the platform
  useful beyond a single web app.
- **Shared infrastructure**: one API can power the frontend, external campus
  integrations, GIS tools, AI clients, analytics, and documentation.
- **Performance with stewardship**: expensive work is cached and reused, while
  source providers are protected from repeated unnecessary traffic.
- **Recoverability**: generated cache data is durable, making Redis a fast layer
  rather than a fragile single point of failure.
- **Operational transparency for maintainers**: Make targets and restricted
  runbooks make common workflows repeatable for approved staff.
- **Future readiness**: MCP, service-tier governance, analytics, durable
  generated artifacts, and cacheable API responses position the platform for
  agentic discovery and wider programmatic use.

## Current Constraints and Future Opportunities

The architecture is strong, but there are natural next steps:

- Add a CDN or edge cache in front of public immutable assets and cached API
  responses for global latency reduction.
- Add a hotset API response warmer for common gallery/search routes after
  nightly sync.
- Continue reducing per-request Elasticsearch and Python work for unique
  searches.
- Add richer dashboarding for cache hit rates, Redis memory, Postgres cache
  growth, and search timing.
- Expand automated tests around operational workflows and cache invalidation.
- Continue documenting service ownership and data lifecycle responsibilities as
  the platform grows.

The overall direction is clear: the system is evolving from a search application
into a durable, cache-aware, API-first geospatial data platform for academic
libraries and research infrastructure.

# Monthly analytics dashboard

The public `/analytics` landing page shows the selected month’s highlights and a report directory.
An analytics-specific header replaces the Geoportal search form and navigation,
with a single link back to the Geoportal. Only the selected report is rendered.

Report links preserve selection in the URL and support reloads and browser history:

| URL | Report | Period |
| --- | --- | --- |
| `/analytics` | Overview, daily activity, and traffic peaks | August 2026 |
| `/analytics?report=comparison` | Portal/member comparisons, daily trends, CSV | July–August 2026 |
| `/analytics?report=content` | Popular resources, collections, downloads (default) | August 2026 |
| `/analytics?report=content&month=2026-07` | Preserved popular-content report | July 2026 |
| `/analytics?report=members` | Alliance and campus detail | August 2026 |
| `/analytics?report=activity` | Legacy alias for Overview | August 2026 |
| `/analytics?report=discovery` | Search terms, filters, zero results | August 2026 |
| `/analytics?report=clients` | Clients, channels, key attribution, MCP/QGIS signals | August 2026 |
| `/analytics?report=platform` | API traffic and reliability | August 2026 |

Unknown report values show the overview. Navigation marks the current report and
wraps on small screens; a skip link leads to the report. All single-month reports default to August and have a month selector. Add
`month=2026-07` to any report URL to view July, or `month=2026-08` for August.
Navigation preserves the selected month. Unknown months fall back to August.
The comparison report always compares both months. Detailed reports show their
period prominently and do not repeat August summary cards. The original July
snapshots remain available within the relevant reports.

The page uses checked-in aggregates, not live queries. Comparison tables show
absolute values, changes relative to July, and downloadable CSV totals. Daily
charts align dates by day of month, with selectable metrics and an exact values
table. Member comparisons have a separate metric selector.

## Snapshot definitions

- July: `frontend/src/data/analytics/july2026.ts` and `memberJuly2026.ts`, exported
  August 20, 2026. These historical values remain unchanged.
- August: `frontend/src/data/analytics/august2026.ts`, exported September 9, 2026.
  Includes timestamps at or after August 1 and before September 1, 2026 (UTC).
- API requests count rows in `analytics_api_usage_logs` by `requested_at`, including
  automated traffic. Server errors have status codes of 500 or higher. Median and
  95th percentile response times use `percentile_cont` over `response_time_ms`.
- Searches and zero-result searches count `analytics_searches` rows and its
  `zero_results` flag. Impressions count `analytics_search_impressions` rows.
- Interactions count `analytics_events` rows. Resource views, result clicks, and
  download clicks count the corresponding `resource_view`, `result_click`, and
  `download_click` event types. Engaged visits count distinct, non-null visit tokens
  in that month's events, not unique people or summed daily distinct counts.
- Daily request, search, and event totals use the same timestamp bounds, grouped
  by UTC calendar date, with zero-filled dates. Each series sums to its summary.
- August member attribution joins resource IDs to the catalog at export, groups
  the first two characters of `b1g_code_s` for codes 01–17, and includes records
  with `publication_state = 'published'` and `gbl_suppressed_b IS NOT TRUE`.
  Source-site clicks count `visit_source_click` events. Member impressions and
  events are aggregated separately before joining, avoiding multiplicative counts.

Member comparisons use each month's exported catalog attribution. Catalog changes
between the two export dates can change the eligible resource set and attribution;
these are snapshot comparisons, not a fixed-cohort measure of campus growth.
Catalog inventory is not presented as an August month-end count.

Percent changes use `(August - July) / July * 100`. A zero baseline with subsequent
activity is `N/A`; two zero values show `0.0%`. Signs indicate numerical direction,
not whether a change is desirable. Both months have 31 days. Downloads are clicks,
not verified completions.

## Validation and updates

Use aggregate exports only; do not check in visit tokens, IP addresses, user
agents, credentials, or raw request records. Production access procedures belong
in restricted operations documentation.

Before adding a snapshot, check timestamp coverage and reconcile daily sums with
monthly totals. Retained July event totals, resource views, and distinct engaged
visits were checked against the preserved snapshot during the August export.
Member attribution can differ when recalculated against a later catalog.

Run from `frontend/`:

```bash
npm test -- --run src/__tests__/pages/AnalyticsPage.test.tsx src/__tests__/components/MonthlyComparison.test.tsx src/__tests__/components/AugustAnalyticsData.test.ts
```

The tests cover displayed comparisons, metric switching, CSV values, zero
baselines, data reconciliation, and full-page accessibility. Also run focused
ESLint/Prettier checks and `npm run build` when changing the page.

## Popular content snapshots

`popularAugust2026.ts` was calculated from events and searches from August 1
inclusive through September 1 exclusive (UTC), exported September 9, 2026.
July's arrays remain unchanged. The month selector updates rankings, totals,
notes, momentum tooltips, dates, and the URL together.

- Resources rank by `resource_view` count. Actions count all other event types.
  Momentum counts all events in days 16–31 versus days 1–15.
- Download rankings count `download_click`, with distinct non-null visit tokens
  per resource. Labels are distinct recorded download labels. August totals are
  812 clicks across 598 resource IDs; the top ten contribute 55 clicks.
- Collection rankings count searches containing collection or local-collection
  inclusion constraints. Both `include_filters[...][]` and `f[...][]` aliases
  are recognized; duplicate values/aliases within one search count once. Exclusion
  filters do not count. A search using multiple collections counts for each.
- Resource rankings join the catalog at export for titles and metadata. Records
  absent from that catalog cannot be ranked by title. All-resource download totals
  include all recorded resource IDs. Ties use resource ID; collection ties use
  kind and filter value. No publication-state restriction is applied to rankings.
- Catalog inventory in the July member report is a point-in-time August 20 count used
  alongside July 1–31 activity. It is not an August activity total or an August 31
  inventory snapshot.

## August detail reports

`reportsAugust2026.ts` contains member, discovery, and API aggregate exports from
September 9. August daily activity and portal totals are in `august2026.ts`.
All activity windows include August 1 and exclude September 1 (UTC).

Member inventory and active-resource counts use the eligible catalog as of
September 9, not a reconstructed August 31 inventory. Active resources are the
union of resource IDs with an event or impression during August, joined to that
catalog. Daily member views/downloads and top-three content use the same eligible
catalog and reconcile with member totals. Leader callouts are calculated from the
selected month's member metrics.

Search terms group trimmed, non-empty queries with a deterministic alphabetical
tie break; zero-result terms also require `zero_results`. View shares use all
searches as denominator. Resource-class filters follow the inclusion-filter
normalization and per-search deduplication described above for collections.

API request mix groups `/api/docs`, `/api/v1/turnstile/status`,
`/api/v1/analytics/events`, and all other endpoints. Peak-day tables add resource,
thumbnail, and crawler categories. The peak day is selected by total requests,
with the earliest date winning ties. Monthly category totals and peak-day
category totals reconcile with their corresponding request counts. Daily peaks,
response percentiles, search shares, donut segments, and descriptive callouts
all follow the selected month.

July datasets are preserved rather than recalculated against today's catalog.

## Clients and API keys

`clients2026.ts` contains aggregates exported September 9 for July and August.
The Clients & API keys report follows the common month selector and provides a
client CSV. It separates three different attribution dimensions:

- Declared `client_name` and `client_channel` identify callers when provided.
  Request counts come from `analytics_daily_api_usage_metrics`; search and event
  counts are grouped independently from their respective raw event tables. Missing
  or blank names/channels are labeled **Not declared**. Counts are not added
  across these different measures.
- API key coverage counts requests with and without `api_key_id`. Both months
  have zero recorded key IDs. This is missing historical attribution, not evidence
  that no API keys were configured or used. The report cannot assign usage to a
  configured key such as `btaa_geoportal`. No key values, hashes, or private key
  owner labels are exported.
- Endpoint surfaces describe requested routes, not client applications. MCP counts
  requests to `/api/v1/mcp` and descendants. OGC routes are not assumed to be QGIS.
  API documentation includes docs, OpenAPI JSON, and ReDoc; access checks include
  status and verification. Thus these categories are broader than the abbreviated
  request mix on the reliability report. Categories are mutually exclusive and
  sum to the monthly request total.

Both monthly request rollups cover all 31 days and match the existing request
summaries exactly. August raw logs independently confirm missing key attribution.
The QGIS signal checks declared client `qgis-plugin` / channel `qgis`, and separately
counts raw user agents containing QGIS (case insensitive). August has no such
matches. July user-agent matching is unavailable because its raw request logs have
expired; its rollups do not retain user agents. Zero matches do not prove zero
QGIS usage. MCP HTTP requests do not measure successful tool calls or individual
WebSocket messages. Application signals can overlap with endpoint categories.

Run the client report tests alongside the dashboard tests:

```bash
npm test -- --run src/__tests__/components/ClientUsageReport.test.tsx src/__tests__/pages/AnalyticsPage.test.tsx
```

### Searches: query rankings and facet usage

The Searches tab follows Popular content and keeps the existing `report=discovery`
URL. `searches2026.ts` contains full-month July and August aggregates exported
September 9. Zero-result rankings include up to 50 trimmed, non-empty queries
with at least three zero-result searches, sorted by count then query text (34
qualifying July rows; 50 August rows shown). Query casing is preserved.

Facet usage counts distinct search IDs per constraint category, combining
`include_filters`, `exclude_filters`, `f`, and `fq` keys. Empty arrays, nulls, and
empty strings are excluded. Nested map bounds and year-range parameters count
once per search and category. Categories overlap, so their totals should not be
summed into a search total. This measures filters present in recorded searches,
not facet clicks. The chart includes geographic constraints alongside facets.

### Shared report presentation

Comparison and client panels use `ReportPanelHeader` for the shared icon, title,
and action layout. Use Lucide outline icons and the analytics color variables.
Table headers, numeric alignment, notes, and panel spacing share rules in
`analytics.css`; preserve text alignment for descriptive columns. Report section
headings stack on narrower screens, and wide tables retain horizontal scrolling.

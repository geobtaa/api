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
URL. `searches2026.ts` combines September 9 facet aggregates with
`zeroResultQueries2026.json`, exported September 10 for the full months of July
and August. Each month now contains its top 100 trimmed, non-empty zero-result
queries, with no minimum-frequency cutoff. Ordering is count descending then
query text ascending using database collation; query casing is preserved.
July has 545 eligible distinct queries and its top 100 represent 268 searches;
August has 885 and its top 100 represent 298. Both rankings end at count two;
one-event queries remain eligible but rank below the top 100. Original published
rows and facet aggregates are unchanged. The JSON download includes the query
ranking export date and coverage separately from the original monthly export date.

Facet usage counts distinct search IDs per constraint category, combining
`include_filters`, `exclude_filters`, `f`, and `fq` keys. Empty arrays, nulls, and
empty strings are excluded. Nested map bounds and year-range parameters count
once per search and category. Categories overlap, so their totals should not be
summed into a search total. This measures filters present in recorded searches,
not facet clicks. The chart includes geographic constraints alongside facets.

See the [August zero-result query review](zero-result-query-review-2026-08.md)
for the completed category inventory of all 100 August queries and linked
recovery issues. Category counts describe this ranking, not every zero-result
search in the month.

The read-only `backend/scripts/export_zero_result_queries_2026.py` exporter
produces top-100 rankings for both months. It removes the
minimum-three cutoff, preserves trimming/case and database alphabetical tie
ordering, and records the distinct eligible query count and ranked event total.
It refuses incomplete or changed history by reconciling search totals,
zero-result totals, and blank/non-blank counts against the published baseline.
Both months are read in one consistent, read-only transaction.

For local development, run from `backend/` against a configured analytics
database with complete monthly history:

```sh
PYTHONPATH=. python scripts/export_zero_result_queries_2026.py --output /tmp/zero-result-queries-2026.json
```

Review query text before publishing this aggregate; it can contain addresses,
coordinates, or names. After a successful export, update the snapshot, report
labels, focused report tests, category inventory, and linked issues together.
The September 10 replacement reconciled all monthly baseline totals and retained
the original ranking prefixes. Deployed database access instructions belong in
restricted operations documentation.

### Shared report presentation

Comparison and client panels use `ReportPanelHeader` for the shared icon, title,
and action layout. Use Lucide outline icons and the analytics color variables.
Table headers, numeric alignment, notes, and panel spacing share rules in
`analytics.css`; preserve text alignment for descriptive columns. Report section
headings stack on narrower screens, and wide tables retain horizontal scrolling.

All analytics line and area series use linear interpolation: straight segments
between recorded daily values, with no smoothing or curved lines.

The data-notes panel offers a JSON download of the selected month's report
aggregates, rankings, daily series, and all member segments. The export includes
period bounds, catalog/export dates, and attribution limitations. It is not a
raw-log or full-catalog download; campus selection does not narrow the snapshot.

## Sources and member grouping modes

Every report includes a visible **Sources and grouping** section describing
its input tables/snapshots, period, grouping rules, and interpretation limits.

Members accepts `grouping=code` (the default historical snapshot) or
`grouping=provider`. These are distinct attribution dimensions:

- Code uses the first two characters of `b1g_code_s`, restricted to 01–17.
  A university bucket includes agency content in that contribution stream.
  Other and missing prefixes were omitted from the original member exports.
- Provider groups exact non-blank `schema_provider_s` values independently of
  codes. Agencies retain their own names; missing/blank providers share a
  Missing provider bucket. Browse links use the exact Provider facet value.
  A federal agency or BTAA-named provider is not automatically mapped to a school.
- The portal-minus-member remainder also includes ineligible/unmatched catalog
  records, so it must not be labeled as an Other-institutions total.
- The harvest-operations report groups harvest records; it also has OpenGeoMetadata,
  licensed databases, BTAA-GIN curated datasets, and Other. Those classifications
  are not inferred from resource titles or copied into catalog attribution.

`providerSnapshots.json` contains July/August Provider aggregates exported
September 10, 2026 against that day's catalog. August has full event and impression
coverage. July's complete original CSV export recovered all 99,482 impressions
across 31 UTC days and 25,719 distinct resource IDs. Durable daily resource
aggregates now supply July's Provider impressions and active-record reach.
Existing historical contribution-code snapshots are preserved.

The code-coverage table uses the same new catalog attribution as Provider mode,
including other/missing prefixes. It is explicitly separate from historical
university charts. Prefix details are shown as stored, without assigning unverified
harvest-operation categories. BTAA-GIN is an exact Provider value; missing Provider
values form their own group.

The read-only `backend/scripts/export_provider_analytics_2026.py` exporter creates
provider metrics, daily series, top content, and contribution-code coverage. For
local development, run from `backend/` with a configured analytics database:

```sh
PYTHONPATH=. python scripts/export_provider_analytics_2026.py --output /tmp/providerSnapshots.json
```

Before replacing the checked-in JSON, review its aggregates, run report tests,
and verify the catalog/export dates. The exporter refuses incomplete event or
impression history for either month by comparing with the original portal
snapshots. It reads impressions from `analytics_daily_resource_impressions`,
which survives raw-data retention. It joins separately aggregated event and
impression counts to avoid
multiplication; provider totals and code-coverage totals must reconcile with the
same eligible catalog. Provider attribution is at the new export date, not a
reconstruction of July/August month-end metadata. Existing code reports and
month-comparison figures retain their original snapshots and dates.


### Table sorting and filtering

All analytics tables use `AnalyticsTable`. Column headings toggle ascending and
descending order; counts and percentages sort numerically, and missing values
remain last in either direction. Text and day labels use natural ordering.
Each table has its own case-insensitive row filter, visible result count, and
Reset button restoring the original report order. Multiple search words must all
appear somewhere in a row. Original ranks and report totals are unchanged.
Filters affect the displayed table only; snapshot/CSV exports remain complete.

The shared component preserves captions, row headers, links, and cell formatting.
Keyboard-operable header buttons expose `aria-sort`, and result counts announce
filter changes. A cell may provide `data-sort-value` when its display requires an
explicit underlying sort value. New analytics tables should use this component.


### Leading Searches report

The Searches page leads with a full-width top-50 query table for the selected
month, ahead of view mix, resource classes, facets and zero-result analysis.
`topSearches2026.json` records rankings and coverage exported September 10 from
complete July/August `analytics_searches` history. Counts include successful and
zero-result searches, trim leading/trailing whitespace, retain case and internal
spacing, and combine filters/views. Empty queries are excluded. Links replay only
query text. Ties use query order under the source database's collation.

`backend/scripts/export_top_searches_2026.py` performs a consistent read-only
export and refuses monthly totals that differ from the preserved baseline.
July has 2,124 searches with query text (1,103 distinct queries); its top 50 account
for 559 searches. August has 3,021 (1,718 distinct); its top 50 account for 652.
The table supports the shared sorting/filter controls. Its full ranking and
coverage are included in the monthly JSON download.


The top-search table expands to show all rows without an internal vertical
scrollbar. Its category column and category selector use reviewed, best-effort
assignments in `queryCategories.ts`. Categories reflect query wording, not
observed intent or catalog metadata. Explicit map/imagery requests take precedence
over place names; clear subjects use topical groups. Place-only terms remain
geographic, and unclear or exclusion-only searches are not forced into a topic.
Case/spacing variants share a category but their source rows/counts are preserved.
Each query belongs to one primary group. Category menu totals cover only the top
50; filtering retains original ranks. Category values and methodology are included
in the monthly JSON download. Unreviewed queries default to Mixed or unclear.


### Academic-year All time view

Monthly reports continue to default to August, the latest published month. The
period selector also accepts `month=all`, preserved across analytics navigation.
All time starts July 1, 2026, the academic-year boundary, and currently includes
published July and August (through August 31 UTC). Partial September is excluded
until published. Month comparison remains the explicit July–August comparison.

`allTime2026.json` is generated by the read-only
`backend/scripts/export_published_analytics_2026.py`. Search/zero-result rankings
are recomputed from complete full-period records; they are not sums of truncated
monthly lists. Daily series retain all 62 calendar dates. Provider/code reach is
deduplicated over the full period, using the September 10 eligible catalog;
inventory is counted once. Client pairs and facet counts can be summed across
these disjoint months. Coverage and methodology appear in the view and download.

The exporter checks published search/event/impression totals, reconciles daily
counts against both snapshots, and checks Provider/code grouping agreement.
Response-time percentiles cannot be combined from monthly percentile summaries;
these, collection rankings and half-month momentum remain monthly features.
Before publishing another month, update the complete monthly dataset, period
coverage/selector, and full-period export together, then rerun reconciliation and
period-switching tests. Do not extend coverage by merging monthly top lists.

### Zero-result outcomes and categories

Monthly and All time Searches reports use the same zero-result section. The
outcome percentage and pie use all searches in the selected period. Table row
percentages use all zero-result searches, not a query-specific failure rate.
The category pie weights each ranked query by its zero-result count and covers
only the displayed top 100 queries; its coverage is stated separately from the
full-period totals. Filtering the table does not change chart denominators.

Categories describe query wording, not proven causes of failure. The reviewed
August classifications are retained; other queries use conservative wording
rules, with an unclassified fallback. Additional original filters can explain
why a query returning results today appears in this report. Query links replay
text only.

## Discovery outcomes and audience coverage

`outcomes2026.json` adds July, August and academic-year aggregates exported
September 10. `export_discovery_outcomes_2026.py` runs in a repeatable-read,
read-only transaction and refuses search/event totals differing from the
published history. Keep this supplemental snapshot alongside the original
monthly reports. Exports include its own export date and period bounds.

Overview leads with search result pages, resource views, source-site clicks and
download clicks. Successful access shows exact monthly bars, including both
months in All time. Popular content has an independent top-50 source-site
ranking, computed over the full selected period rather than a subset of viewed
resources. All time download rankings use the same full-record scope. Source
clicks are `visit_source_click`, not every outbound event. Counts include
unmatched catalog records; a left join supplies labels without dropping clicks.
July has 1,129 source clicks and 933 downloads; August has 858 and 812.

Tracked visits deduplicate nonblank visit tokens across searches and events.
These tokens are stored in browser sessionStorage: they are tab-scoped, not
persistent visitors or inactivity-based sessions. July has 7,729, August 13,020,
and the combined period 20,735; the monthly counts cannot be added because tokens
can span months. Daily distinct totals likewise must not be added. There are
120 activity records without tokens across the two months. All recorded searches
and events declare `geoportal-web` / `browser`; this is caller attribution, not
proof of human activity. Searches count rendered result pages, including
pagination/filter changes, rather than only new typed queries.

Unique visitors and general pageviews are shown as **Unavailable**, not zero.
No persistent visitor identifier or general `page_view` event coverage exists in
these historical snapshots. Resource views describe detail pages only. The
existing GTM `virtual_page_view` dispatch on React Router navigation is not
verification that deployed GTM maps it to GA4 pageviews. GA4/GTM deployment and
Realtime validation remain separate from this database-backed reporting.

Failed-query rows now expose aggregated saved parameter combinations for each
ranked term, with counts, included/excluded facets, page/view/sort/search field,
and original result totals. Replay links preserve exported parameters, not just
query text. Only allowlisted search controls and public facet keys are exported;
visitor tokens, raw URLs and arbitrary tracking/authentication parameters are not.
Blank-query context is available separately. Details are loaded into the DOM when
expanded. Context can be filtered even while collapsed; its column sorts by the
number of recorded combinations.

The published zero-result flag was based on an empty displayed page. August has
two flagged rows with positive total-result counts; July has none. Preserve the
published totals and explain this distinction rather than silently rewriting
history. All four August `redlining` zero-result events had exclusion filters.
Three stored parameter combinations represent these events; ordering differences
in arrays are preserved. Replaying them against today's catalog may differ.

### Remaining measurement work

To provide unique visitors or all-pageview trends, select a validated collection
source and define its identity/session rules, consent behavior and reporting
coverage first. Historical tab tokens cannot reconstruct unique people. The
current dashboard implements the available audience measures and explicitly
states the gaps; it does not claim GA4 parity or completed-download measurement.

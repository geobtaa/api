# Monthly analytics dashboard

The authenticated `/analytics` landing page shows the selected month’s highlights and a report directory.
An analytics-specific header replaces the Geoportal search form and navigation,
with a single link back to the Geoportal. Only the selected report is rendered.

Report links preserve selection in the URL and support reloads and browser history:

| URL                                       | Report                                               | Period           |
| ----------------------------------------- | ---------------------------------------------------- | ---------------- |
| `/analytics`                              | Overview, daily activity, and traffic peaks          | September 2026   |
| `/analytics/comparison`            | Monthly totals, chart, CSV/JSON downloads         | July–September 2026 |
| `/analytics/content`               | Popular resources, collections, downloads  | September 2026   |
| `/analytics/content?month=2026-07` | Preserved popular-content report                     | July 2026        |
| `/analytics/members`               | Alliance and campus detail                           | September 2026   |
| `/analytics/activity`              | Legacy alias for Overview                            | September 2026   |
| `/analytics/discovery`             | Search terms, filters, zero results                  | September 2026   |
| `/analytics/clients`               | Clients, channels, key attribution, MCP/QGIS signals | September 2026   |
| `/analytics/platform`              | API traffic and reliability                          | September 2026   |

Unknown report paths return 404. Legacy `?report=...` links redirect to report paths,
preserving the month and other query parameters. `/analytics` is Overview;
`/analytics/overview` and `/analytics/activity` redirect there. Navigation marks the current report and
wraps on small screens; a skip link leads to the report. Single-month reports
default to September. Use `month=2026-07`, `month=2026-08`, or `month=2026-09`
to select a month, or `month=all` for July–September. Navigation preserves the
selected period. Unpublished periods show an unavailable message. The comparison
report shows all three months.

The page uses checked-in aggregates, not live database queries. September and
refreshed cumulative reports include full CSV/JSON table downloads in ZIP files.
See the [September update](#september-2026-update) for their source coverage and
local regeneration workflow. The sections below describe the original July and
August snapshot definitions and presentations, which remain available.

## Summary widget styling

Use `analytics-metric-card` for summary widgets on every dashboard report.
It supplies the white surface, BTAA blue left border, padding, heading, value,
and explanation styles. Keep page-specific classes for grid layout only; do
not add alternate card colors or typography. Use `MetricHeading` when a metric
has an icon, followed by a direct `strong` value and `p` or `small` explanation.
The print-oriented campus brief retains its separate compact layout.

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

### Rebuilding cumulative collection rankings

Generate collection-filter counts from preserved monthly reporting archives with
`PYTHONPATH=backend python backend/scripts/export_collection_searches.py /path/to/month1.json.gz /path/to/month2.json.gz --output /path/to/collection-counts.json`.
Supply one archive revision per month. The output records source checksums and
preserves the complete collection ranking; the dashboard selects the top 50
after aggregation. Collection IDs unify legacy `dct_isPartOf_sm` and
`pcdm_memberOf_sm` controls. Local collection labels remain separate. Include,
exclude, and legacy controls count once per search per collection; overlapping
collections do not represent distinct searches overall. This rebuild uses the
collection controls retained in the archives, rather than summing monthly top
lists. It does not export free-text queries or visitor identifiers.

### Shared Members and Overview layouts

Members and Overview render the same components for monthly and All time periods,
including their selectors, charts, tables, and local navigation. Date ranges and
daily-series lengths come from the selected period. All time visit counts use the
saved full-period distinct count, never the sum of monthly counts.

The Members adapter reads a restricted aggregate projection of a preserved report.
To refresh that projection locally:

```sh
python backend/scripts/export_member_report.py /path/to/report-all.json --output frontend/src/data/analytics/memberAllTime2026.json
```

The projection includes member/provider counts, daily views and downloads, and
the leading three resources for each metric after full-period aggregation. It
excludes searches, tokens, request parameters, and other unrelated report fields,
and records a source checksum. Full rankings remain in the preserved input.
Do not add monthly inventory or active-record counts to create cumulative counts.

The preserved code mapping excludes four-digit federal codes from Wisconsin's
university code 10; the older monthly snapshots used a broader prefix match.
The All time report discloses this distinction and incomplete July impression
evidence. Original monthly snapshots remain unchanged.

Searches also uses a single layout for monthly and All time views: top 50 queries,
daily search counts, search-view mix, resource-class demand, facet usage, and
zero-result details. Cumulative query rankings and distinct-query totals use the
preserved full-period export; they are not reconstructed from monthly top lists.
Facet and resource-class counts sum disjoint monthly periods, and cumulative
view percentages are recalculated from counts. Daily values retain UTC dates.

Clients & API keys shares its monthly layout with All time. Matching declared
client/channel pairs and endpoint categories combine across disjoint months;
request shares are recalculated using cumulative requests. Missing user-agent
evidence remains unavailable across the combined period. Distinct key counts
are never summed: without key identities, only an all-zero history can report
zero recorded keys; otherwise the combined count is unavailable.

API reliability uses the same summary, request mix, peak-day breakdown, daily
chart, and endpoint table for every period. Cumulative request/error totals and
request-mix percentages are recalculated from counts. Median and p95 remain
unavailable for All time because monthly percentiles are not mergeable.

`reliabilityEndpoints2026.json` preserves August route aggregates and derives
July counts for routes present in the saved full-period list by subtracting
August. The saved list is incomplete: unmatched requests and errors remain in
an explicit Other / unlisted routes bucket. Each period reconciles against
complete daily rollups; the table does not claim a complete route-level history.

Every report header uses `ReportingPeriodPicker` at the top right, including
All time views. Month comparison displays its fixed July–August comparison
period in the same position; it does not offer a single-month selection that
would leave comparison data unchanged.

## September 2026 update

The default dashboard period is September 2026. The September snapshot covers
September 1 inclusive through October 1 exclusive (UTC), with activity on all 30
days. Its October 9 export reconciles 475,908 API requests, 5,536 search result
pages, 90,683 impressions, and 14,509 interactions. Those interactions include
10,497 resource views, 876 download clicks, and 882 source-site clicks.

September and the refreshed All time report use the established `AnalyticsPage`
layout, charts, content cards, campus selectors, and searchable tables. A data
projection converts preserved reporting inputs to those components’ existing shapes. The static files live under
`frontend/private-analytics-reports/`; their manifest identifies exact revisions.
July and August retain their original monthly presentations and source snapshots.
The comparison report now includes all three months. Cumulative data are rebuilt
from the complete preserved monthly inputs, never from displayed top lists or by
adding distinct visit counts. Historical gaps remain explicitly unavailable.
Catalog attribution uses each input's recorded capture date; September's catalog
was captured October 9, not at September month-end.

Rankings and member previews retain the established presentation limits. Each report
provides a ZIP download containing the complete public report and its CSV/JSON
tables, with the existing query disclosure policy and CSV formula escaping.
Raw tokens, IP addresses, and preservation receipts are not public downloads.
The static report delivery does not enable the shadow runtime API or certify
production archive durability, retention, or automated monthly publication.

To regenerate locally from reconciled private archives:

```bash
python backend/scripts/export_analytics_snapshots.py /path/to/july.json.gz /path/to/august.json.gz /path/to/september.json.gz --through 2026-10-01 --period 2026-09 --period all --output frontend/private-analytics-reports
```

After that export, run `backend/scripts/export_analytics_design_data.py` with the
same archive paths, `--public frontend/private-analytics-reports`,
`--output frontend/src/data/analytics`, and `--supplemental /path/to/verified-counts.json`.
The supplemental aggregate file provides search counts, distinct non-empty query
counts, zero-result searches with query text, and September event-only engaged
visits. These preserve the original comparison definitions without substituting
HLL audience estimates. Original July/August source files are unchanged.

The exporter validates archive receipts, rejects duplicate or missing months,
and reconciles additive daily totals before writing the manifest. Keep private
archives outside tracked source files. Production extraction and preservation
procedures belong in the restricted operations documentation.

## Popular content ranking depth

Popular content shows up to 50 Resources, Collections, Downloads, and Outlinked
resources for every published month and All time. Rankings are selected from
complete preserved aggregates, not extended from earlier top-ten lists.
`export_analytics_design_data.py` also emits `popularHistory2026.json` for the
expanded July/August resource, collection, and download rankings. Original source
snapshots remain unchanged; fewer than 50 entries appear only when fewer qualify.

## Content metadata corrections

Content labels use resource metadata independently of publication state and
campus inventory eligibility. `Provider not recorded` is used only for an empty
Provider field; missing metadata uses `Provider metadata unavailable`.
The title falls back to the resource ID only when no title can be recovered.

`backend/scripts/refresh_analytics_metadata.py` accepts reconciled private archives,
`--metadata /path/to/metadata.json.gz`, and `--output /path/to/new-revisions`.
The metadata input contains `capturedAt` and a `catalog` mapping resource IDs to
`title`, `provider`, and optional `attributes`. This creates new checksummed
revisions and preserves all activity rows, receipts, visits, and original campus
eligibility. Content corrections live alongside the historical member metadata,
with their own capture date and source checksum; they do not rewrite old archives.
Then regenerate public snapshots for July, August, September, and All time with
`export_analytics_snapshots.py`, followed by `export_analytics_design_data.py`.
The dashboard and downloadable reports use these corrected labels. Keep input
metadata and archive files private and extraction instructions in restricted docs.

## Repeatable monthly refresh

The dashboard now discovers reporting periods from the generated manifest.
Every month from September 2026 onward uses the same adapter and established
layouts; month selection, comparison columns, day counts, and year labels do not
require a new component. July/August keep their historical definitions. All time
is rebuilt from complete inputs, including full rankings and distinct-count
information, rather than by adding displayed top lists or distinct visitors.

From the repository root, with the project Python environment active:

```sh
make analytics-monthly-update ARCHIVES='/path/to/verified/*.json.gz' SUPPLEMENTAL=/path/to/verified-counts.json
make analytics-monthly-check
cd frontend && npm run build
```

The default boundary is the first day of the current UTC month, so only completed
months are included. For a reproducible rerun, add `THROUGH=2026-10-01` to regenerate
through September. Supply exactly one reconciled, checksummed archive for every
month since July 2026, using metadata-corrected revisions where available.

Supplemental JSON must include an object for each month from September onward
and `all`, with `searches`, `with_query`, `distinct_queries`, and `zero_with_query`.
Each monthly object also requires `engaged_visits`: the exact distinct count of
non-null event visit tokens, never a sum of daily counts or an audience estimate.
The `all` object covers the entire requested range. Keep these inputs private.

The command builds reports and presentation data in a temporary directory and
validates all inputs before replacing generated files. Failed generation leaves
the existing dashboard in place. Repeated runs with the same inputs produce the
same data and report revisions. File installation is for a local checkout; it
is not a transactional live deployment. Do not run concurrent refreshes in one
checkout or serve a build while files are being installed.

Before publication, review any new Top 50 query terms in `queryCategories.ts`.
The monthly check fails for unreviewed terms, including All time; classify real
ambiguities explicitly rather than letting new terms fall through silently.
Also check resource titles/provider metadata, monthly daily sums, all published
periods, downloads, and the established report layouts. Historical coverage gaps
remain disclosed. A successful local refresh does not enable deployment.

Automated source collection, durable archives, access setup, deployed scheduling,
and publication are restricted operations material. Maintain those steps in the
restricted operations runbook. The local command deliberately needs verified
inputs; missing source data must fail visibly rather than publish a partial month.

### Report heading consistency

The right-hand section navigation reads the visible section/panel headings, so
changing a title also changes its navigation label. Separate navigation aliases
do not override the heading. Overview highlight cards contain metrics without
decorative numbering. Shared Sources and grouping notes use a two-column table
with row headers for Source, Grouping, and Reading the figures.

## Download privacy contract

The aggregate report download uses privacy version 2. Both the ZIP's JSON/CSV
files and its public `report.json` sidecar use an explicit field and type allowlist
in `analytics_reporting/public_export.py`. The export retains numeric portal
metrics, calendar-day and month totals, fixed search categories, latency, and
aggregate visit estimates. It excludes search terms and contexts, IP addresses,
visit tokens, user agents, raw request paths, client/key labels, resource IDs and
metadata, download labels, and all unknown fields. Adding a report dimension does
not automatically publish it. Text screening and a minimum query frequency are
not a guarantee that search terms are anonymous.

The monthly exporter applies this contract automatically. The dashboard adapter
builds its separate presentation input from private archives in memory, rather
than relying on detail in the public download. This contract covers report
artifacts and runtime report downloads; the dashboard's separate presentation
snapshots require their own privacy review when their content changes.

The privacy update removes all seven previous static revisions from the served
source directory and creates new aggregate-only revisions. Rebuild the frontend
to remove stale build copies. Removing served files does not erase earlier Git
history, previously downloaded copies, or deployment/CDN caches. Any publication
cleanup belongs in the restricted operations documentation.

The Month comparison report leads with monthly activity bars, switchable between
monthly totals and calendar-day averages. Daily trends use overlaid lines with
distinct colors and dash patterns; absent dates remain gaps. The heading covers
all published months, while table change columns explicitly name the latest two.

Popular content momentum compares a resource's view count with the previous
calendar month's complete resource-view report. July has no prior-month baseline;
zero prior views are labelled explicitly without inventing a percentage. Exported
`previousMonthViews` values are reproduced from the private archive during monthly
updates. Class/type charts currently summarize the displayed top-resource cohort,
not the full catalog; their captions state that scope and disclose overlapping
classifications. Rank bars use the largest count in the full displayed ranking,
so filtering does not change their scale.

Thumbnail requests use the same-origin thumbnail proxy, including cached-image
redirects. For a local preview, set `API_BASE_URL` to the actual local API port
when it differs from the default 8000. Resources without an available preview
retain the resource-class fallback icon.

Popular content collection rankings use member-resource view events, attributed through each month's saved collection membership. All Time aggregates the complete monthly inputs before ranking; it does not sum truncated top lists. Multi-collection resources contribute to each collection, and missing memberships remain unattributed. Collection-filter search counts are a separate metric.

All monthly Popular content rankings display percent change against the previous calendar month for their own metric. Collections, downloads, and outlinks use complete preserved prior-month counts before truncation; a missing item in a known baseline means zero, while a missing month means unavailable. Classification momentum compares the current top-resource cohort using the same classification assignments in both months, matching the scoped chart totals. Zero baselines display No prior activity instead of a percentage. All Time omits momentum entirely.

Collection title corrections are preserved in collectionTitlesCurrent.json with their catalog lookup date. The view-ranking export uses these verified public labels only when the sealed catalog lacks a usable title; archived titles take precedence and view counts remain unchanged. New exports capture all catalog records, including collection records.

## Analytics sign-in

The sign-in page follows `DESIGN.md`: the shared analytics brand header, BTAA/GIN
logo assets, theme colors, shared primary CTA styles, and responsive page gutters.
Report navigation appears only on the authenticated dashboard; login confirmation
and error states retain the same institutional layout.

All analytics pages require a session established with a shared password. Set
`ANALYTICS_PASSWORD` in the API's local environment to a randomly generated value
of at least 20 characters. Empty or shorter settings disable sign-in. Never
commit the password. `ANALYTICS_BASE_URL` must match the browser origin; the local
default is `http://localhost:3000`. Non-local origins require HTTPS.

The password is sent by same-origin POST, compared on the server in constant time,
and never returned in the page or stored in Redis. Thirty sign-in attempts are
allowed per 15-minute window across the application; this shared budget cannot be
bypassed with forged forwarding headers. Redis stores hashes of opaque session
tokens. Sessions last 24 hours; signing out invalidates the session immediately.
Changing the password and restarting the API invalidates all existing sessions.
A missing password or unavailable Redis denies access. Shared sessions do not
identify individual people. Email-link and Google sign-in routes are removed.

Snapshot modules are imported only by `app/lib/analytics-data.server.ts`. The
authenticated route loader supplies their serializable values through
`AnalyticsDataContext`; data-dependent helpers operate on that payload. Vite
rejects client imports of snapshot modules. Historical aggregates remain in
source control; this access boundary protects application delivery and does
not remove previously published copies or Git history.

Archived JSON and ZIP files live in `frontend/private-analytics-reports`, outside
the public asset directory. `/analytics-reports/*` validates the session and
serves only known report filename patterns. The runtime reporting API checks the
same session for manifests, report revisions, and CSV/JSON downloads. Its
existing shadow-validation switch still applies after authentication. Public
event ingestion and admin authentication remain separate.

Report and login responses use `private, no-store`, including redirects to sign
in. The session cookie is HttpOnly, host-only, SameSite=Lax, and Secure outside
local development. Passwords are submitted only by POST. Google Tag Manager is not loaded
on analytics pages. Password distribution and deployment procedures belong in
restricted operations documentation.

Run the authentication checks with the focused backend tests in
`tests/services/test_analytics_auth.py` and frontend tests in
`src/__tests__/analyticsAuth.test.ts`, alongside the dashboard component tests
and a production frontend build. The build must not contain an
`analytics-reports` public directory or embedded snapshot data.

### Searches report layout

The Searches report begins with daily search activity and a category pie chart.
The pie counts search events represented by the top 50 query terms, not the
entire search log; its legend includes exact counts and shares. Both charts
follow the selected reporting period and stack on narrow screens. Top Searches
uses the shared Popular content ranking rows and retains category filtering.

Zero-result searches use summary cards for total failures, failures with query
text, and filter-only failures. A compact outcome bar covers the full period;
category bars explicitly cover only the ranked query subset and describe wording,
not verified causes. Ranked rows share the Popular content layout, support query
and context filtering, and retain expandable recorded search combinations.
Methodology is available under “About these counts.”

English readings for saved non-English zero-result queries live in
`frontend/src/data/analytics/queryTranslations.json` and are delivered with the
authenticated report payload. They are editorial translations or transliterations,
not live machine translation. Preserve original query links and mark ambiguous
names or incomplete phrases. The query filter also matches the English reading.

The Searches report uses `/analytics/searches`. Existing `/analytics/discovery`
links redirect to it, preserving the selected period and other query parameters.

The Members campus selector uses the full partner roster, including USC. A partner
without a saved contribution-stream group shows an explicit unavailable state;
missing data is not counted as zero or substituted with alliance totals. Grouping
and period controls sit together in the report header.

Members Leading Content shows up to 50 viewed and 25 downloaded resources per
institution and period. `memberLeadingContent.json` is generated from complete
private `memberResources` aggregates by the design-data exporter and delivered
only with the authenticated snapshot. Alliance rankings deduplicate resource IDs
before selecting the top 50 viewed and top 25 downloaded; institutions with fewer qualifying resources show
only those available.

### Verified Geoportal request attribution

The configured unlimited Geoportal key is authenticated independently of database
key records. Its requests are queued for API usage logging even when authentication
returns no database tier ID. The background writer resolves the named service tier
before insertion; it retries storage failures using the existing task policy.
Authentication and unlimited access do not depend on this analytics lookup.

Logs carry a server-assigned `authenticated_identity` property for that key.
The authentication path also queues the verified key’s current and legacy lookup hashes.
The writer resolves the existing registry ID and name, updates last-used time,
and removes those transient hashes before inserting the analytics record.
Reporting uses the resolved key ID; unmatched registry entries retain an explicit
verified-Geoportal label and generate a warning. Raw credentials are never queued.
Captured hashes identify the request’s key even if configuration rotates before
the worker handles it. Existing inactive registry entries are not reactivated. Caller-supplied client/channel headers remain
separate. Requests without a client name default to `geoportal-ssr` only after
the configured key is verified. The frontend server helper also supplies SSR
labels by default and preserves explicitly forwarded browser labels.

July–September snapshots retain their recorded values. Missing identity headers
and the previous unlimited-key logging bypass mean these reports cannot measure
total Geoportal key usage. “Not declared” must not be reassigned to SSR, and absent
requests cannot be recovered by relabeling aggregates. The Clients report explains
these gaps. New logging applies after the updated API and worker are deployed;
deployment verification belongs in the restricted operations runbook.

### Refresh and regression checks

The staged monthly refresh installs `memberLeadingContent.json` together with
the other generated data before switching the report manifest. This keeps the
member rankings and cumulative summaries on the same reporting boundary.
The successful-refresh test covers a fourth month and replacement of prior
cumulative rankings, in addition to the existing failure-preservation checks.

Snapshot period selection is shared between metadata and page rendering.
Missing, malformed, or unpublished snapshot periods fall back to the latest
published month; `all` retains cumulative selection. Runtime period selection
uses its own live manifest and explicitly reports unavailable periods.

Analytics tests share structural chart mocks and a data-router wrapper for
components containing the sign-out form. Chart-specific tests may override the
shared mocks. Assert DOM collection counts as numbers so failed assertions do
not serialize entire report trees.

The full analytics page suite uses jsdom for axe compatibility with escaped
selectors in quoted query labels. Its router wrapper disposes history listeners
on unmount so repeated navigation tests do not retain prior page trees.

### Answering questions about the numbers

Open **Data provenance and coverage** at the bottom of a report and download the
report evidence packet. Share its readable summary with the exact report revision;
the included report JSON and daily CSV allow colleagues to check totals themselves.
The evidence distinguishes reproduced inputs from independently verified source
completeness. July and cumulative reports retain their incomplete coverage label.
See [report evidence packets](analytics-runtime-reporting.md#report-evidence-packets)
for scope, definitions, limitations and local regeneration.

### Meeting briefs

The overview leads with activity measures and charts. It does not display
automatically selected narrative findings.

In Members, select the contribution grouping, reporting period and institution,
then choose **Open campus brief**. The `brief=1` view preserves the selected period
and institution in its URL. Activity measures appear in this order: views,
impressions, source-site clicks and download clicks. The brief includes raw count
changes from the prior calendar month when available, catalog reach, days with
views, a daily trend, and five view/download leaders from the member report.
Popular collections shows the top three collections by views of the selected
campus's resources. The monthly exporter derives `memberCollectionViews.json`
from complete preserved view dimensions, eligible contribution-stream attribution
and collection membership for each month. Cumulative rankings sum those monthly
assignments. Resources in multiple collections contribute to each collection;
unmapped or ineligible resources are excluded. Rankings are delivered through the
authenticated analytics payload and refreshed with the other dashboard data.
All recorded contributions can also be summarized together. Unavailable campuses
and Provider grouping do not offer a brief.

**Copy brief link** retains the selected context; recipients still need analytics
access. **Print / save PDF** invokes the browser print dialog. Dedicated print
styles remove controls and arrange the brief for a portrait page, retaining the
period, catalog date, a short activity-count note and a linked revision identifier.
Detailed aggregation and evidence-scope explanations remain in the full report
and evidence packet rather than occupying the brief.
Printer paper size, scaling and browser headers/footers can affect pagination.
Aggregate evidence does not certify the brief's member attribution or rankings.

## Language for library audiences

Dashboard headings, summaries, and campus briefs address librarians and library
directors. Name the recorded measure rather than implying impact or intent:
“resource views,” “download clicks,” “search appearances,” and “resources with
activity.” A search appearance means a resource appeared in results. It is not
a view, a distinct visitor, or evidence of research impact. Download rankings
must say “download clicks,” not “most downloaded.”

Explain institution groupings as responsibility for contributing resources or
the provider named in the catalog; keep the underlying contribution codes and
API fields unchanged. Use everyday wording in visible summaries and keep
technical definitions, identifiers, and evidence available in the report
notes. Missing records are unavailable, never zero. Keep monthly and cumulative
views consistent, and preserve precise limits on what verification establishes.

### Summary tab

Discovery activity shows Visits, Searches, and Resource views in three chart
cards, stacked on smaller screens. Resource views sum the saved daily view
counts for the selected period; incomplete daily coverage remains unavailable.

`/analytics/summary` uses authenticated saved snapshots in a centered content
column capped at 72rem. Its period picker offers published months and all time,
with the latest three calendar months offered only while the published all-time aggregate
matches that exact window. Summary defaults to that three-month window when
available, otherwise to the latest published month. Older `month=3months` links
also select the latest month when the shortcut is unavailable. This keeps visits
and rankings populated after a fourth month is published without adding distinct
visits or truncated rankings across months. The same period selection is used
for the picker, report metadata, and displayed figures. Explicit period choices
are saved in the URL. Query terms are hidden behind **Show query terms**;
opening each list reveals all saved queries with their suggested category and
search count. Each list closes when the period changes. Resource rankings show
five entries by default and expand to up to 20. Outlinks and
downloads show a period total and at most 12 vertical bars, with exact counts
above the bars and a collapsible **Monthly values** list. Up to 12 months use
monthly bars; 13–36 months use calendar quarters; longer periods use calendar
years. A window touching more than 12 calendar quarters switches to years.
Histories spanning more than 12 calendar years use consecutive groups of years
to retain the whole period within 12 bars. The chart labels its grouping and
marks incomplete quarters, years, or groups of years as partial. Missing monthly
counts make the corresponding grouped count unavailable rather than zero.
Popular resources use ranked titles and aligned click counts without bars.

Most common and No-result searches each include a category pie chart and count
legend above their term rankings, using the same category rules as the Searches
report. Categories cover all saved leading queries for the selected period,
including those in the collapsed term lists. Counts and percentages describe
that saved sample, not all searches. Expanding a term list does not change the
chart. Periods without matching rankings also have no category chart.

- Visits use the period-wide distinct count; daily estimates are not additive.
- Rankings require an aggregate matching the selected dates. Adding truncated
  monthly rankings would produce incorrect totals and ordering.
- Collection growth reuses the Members provider report's inventory and capture
  date. Net and percentage changes compare the latest strictly earlier capture,
  not the activity month. They include removals and publication changes.
- Missing measurements remain unavailable, never zero. Download clicks do not
  verify completed transfers.
- Current saved Outlink counts and access percentages exclude
  `licensed_access_click` events. Summary keeps a short note beside its access
  totals explaining that the exclusion also affects resource rankings, using
  plain language alongside the director-facing headings. The Content report
  displays a temporary disclaimer in an amber callout until the
  reporting aggregation includes them as outlinks and the historical snapshots
  are regenerated from preserved data.

## Experimental views and access clicks

The Content tab includes **Views and access clicks** below its resource rankings.
This experimental section and its temporary Licensed Access disclaimer were moved
from Summary so that Summary stays focused on overall activity.

Two five-record samples compare fewer and more access clicks per view, using
only the saved leading-resource rows with at least 20 views. The current export
contains 50 resources, not the whole catalog. Monthly snapshots lack the combined
counts and show an unavailable state instead.

Rows show views, outlinks, downloads, and combined clicks divided by views,
formatted as a percentage. Rank by that ratio, then higher view count
and resource ID for stable ties. The higher-ratio list requires a click. Ratios
can exceed 100% and do not measure visit conversion or record quality. No new
tracking or backend endpoint is introduced.

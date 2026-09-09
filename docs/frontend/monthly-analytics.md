# Monthly analytics dashboard

The public `/analytics` landing page shows August highlights and a report directory.
An analytics-specific header replaces the Geoportal search form and navigation,
with a single link back to the Geoportal. Only the selected report is rendered.

Report links preserve selection in the URL and support reloads and browser history:

| URL | Report | Period |
| --- | --- | --- |
| `/analytics` | Overview | August 2026 |
| `/analytics?report=comparison` | Portal/member comparisons, daily trends, CSV | July–August 2026 |
| `/analytics?report=content` | Popular resources, collections, downloads | July 2026 |
| `/analytics?report=members` | Alliance and campus detail | July 2026 |
| `/analytics?report=activity` | Daily activity and traffic peaks | July 2026 |
| `/analytics?report=discovery` | Search terms, filters, zero results | July 2026 |
| `/analytics?report=platform` | API traffic and reliability | July 2026 |

Unknown report values show the overview. Navigation marks the current report and
wraps on small screens; a skip link leads to the report. Detailed reports show their
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
npm test -- --run src/__tests__/pages/AnalyticsPage.test.tsx src/__tests__/components/MonthlyComparison.test.tsx
```

The tests cover displayed comparisons, metric switching, CSV values, zero
baselines, data reconciliation, and full-page accessibility. Also run focused
ESLint/Prettier checks and `npm run build` when changing the page.

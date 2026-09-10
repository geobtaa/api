import {
  AccessSummary,
  AudienceReport,
  OutlinkedResources,
} from './DiscoveryOutcomes';
import { outcomes } from '../../data/analytics/outcomes';
import { ZeroResultReport } from './ZeroResultReport';
import zeroSnapshots from '../../data/analytics/zeroResultQueries2026.json';
import { Seo } from '../Seo';
import { useState, type ReactNode } from 'react';
import { Link, useSearchParams } from 'react-router';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  BarChart,
  Bar,
} from 'recharts';
import { Activity, Table2 } from 'lucide-react';
import data from '../../data/analytics/allTime2026.json';
import {
  clientSnapshots,
  type ClientUsage,
} from '../../data/analytics/clients2026';
import { searchSnapshots } from '../../data/analytics/searches2026';
import { memberPerformance } from '../../data/analytics/july2026';
import {
  queryCategory,
  queryCategoryMethod,
} from '../../data/analytics/queryCategories';
import { FACET_LABELS } from '../../utils/facetLabels';
import {
  analyticsReports,
  type AnalyticsReport,
} from '../../config/analyticsReports';
import { AnalyticsHeader } from './AnalyticsHeader';
import { AnalyticsTable } from './AnalyticsTable';
import { ReportPanelHeader } from './ReportPanelHeader';

const number = new Intl.NumberFormat('en-US');
const range = 'July 1–August 31, 2026';
type DailyMetric =
  | 'requests'
  | 'searches'
  | 'zeroResults'
  | 'events'
  | 'views'
  | 'downloads'
  | 'errors';
const labels: Record<DailyMetric, string> = {
  requests: 'API requests',
  searches: 'Searches',
  zeroResults: 'Zero-result searches',
  events: 'Interactions',
  views: 'Resource views',
  downloads: 'Download clicks',
  errors: 'Server errors',
};
const dayLabel = (day: string) =>
  new Date(`${day}T00:00:00Z`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
const clients = new Map<string, ClientUsage>();
for (const snapshot of data.publishedMonths.map(
  (month) => clientSnapshots[month as keyof typeof clientSnapshots]
))
  for (const client of snapshot.clients) {
    const key = JSON.stringify([client.name, client.channel]);
    const old = clients.get(key) ?? {
      ...client,
      requests: 0,
      searches: 0,
      events: 0,
    };
    clients.set(key, {
      ...old,
      requests: old.requests + client.requests,
      searches: old.searches + client.searches,
      events: old.events + client.events,
    });
  }
const facets = new Map<string, number>();
for (const snapshot of data.publishedMonths.map(
  (month) => searchSnapshots[month as keyof typeof searchSnapshots]
))
  for (const facet of snapshot.facets)
    facets.set(facet.field, (facets.get(facet.field) ?? 0) + facet.count);

function Table({
  title,
  heading,
  headers,
  rows,
}: {
  title: string;
  heading?: string;
  headers: string[];
  rows: ReactNode[][];
}) {
  return (
    <section className="analytics-panel analytics-comparison-panel">
      <ReportPanelHeader title={heading ?? title} icon={Table2} />
      <div className="analytics-comparison-scroll">
        <AnalyticsTable className="analytics-comparison-table">
          <caption className="sr-only">{title} · All time</caption>
          <thead>
            <tr>
              {headers.map((label) => (
                <th scope="col" key={label}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index}>
                {row.map((value, column) =>
                  column === 0 ? (
                    <th scope="row" key={column}>
                      {value}
                    </th>
                  ) : (
                    <td key={column}>
                      {typeof value === 'number' ? number.format(value) : value}
                    </td>
                  )
                )}
              </tr>
            ))}
          </tbody>
        </AnalyticsTable>
      </div>
    </section>
  );
}

function Trend({ metrics }: { metrics: DailyMetric[] }) {
  const [metric, setMetric] = useState(metrics[0]);
  return (
    <section className="analytics-panel analytics-comparison-panel">
      <ReportPanelHeader title="Daily totals" icon={Activity}>
        <label>
          Chart metric{' '}
          <select
            value={metric}
            onChange={(event) => setMetric(event.target.value as DailyMetric)}
          >
            {metrics.map((key) => (
              <option key={key} value={key}>
                {labels[key]}
              </option>
            ))}
          </select>
        </label>
      </ReportPanelHeader>
      <div
        role="img"
        aria-label={`${labels[metric]} across ${range}. Exact daily values follow.`}
      >
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data.daily}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="day" tickFormatter={dayLabel} minTickGap={35} />
            <YAxis />
            <Tooltip labelFormatter={(value) => dayLabel(String(value))} />
            <Line
              type="linear"
              dataKey={metric}
              name={labels[metric]}
              stroke="#003c5b"
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details>
        <summary>Daily values</summary>
        <Table
          title="Daily values"
          headers={['Date', ...metrics.map((key) => labels[key])]}
          rows={data.daily.map((day) => [
            day.day,
            ...metrics.map((key) => day[key]),
          ])}
        />
      </details>
    </section>
  );
}

function Searches() {
  const [category, setCategory] = useState('all');
  const queries = data.queries.map((query, index) => ({
    ...query,
    rank: index + 1,
    category: queryCategory(query.term),
  }));
  const categories = [...new Set(queries.map((q) => q.category))].sort();
  return (
    <>
      <h2>Top 50 searches</h2>
      <p>
        {number.format(data.searchTotals.withQuery)} searches with query text ·{' '}
        {number.format(data.searchTotals.distinctQueries)} distinct queries
        across {range}.
      </p>
      <label className="analytics-query-category-filter">
        Query category
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          <option value="all">All categories</option>
          {categories.map((name) => (
            <option key={name}>{name}</option>
          ))}
        </select>
      </label>
      <Table
        title="Top 50 searches"
        heading="Most frequent queries"
        headers={['Rank', 'Query', 'Category', 'Searches']}
        rows={queries
          .filter((q) => category === 'all' || q.category === category)
          .map((q) => [
            q.rank,
            <Link to={`/search?q=${encodeURIComponent(q.term)}`}>
              {q.term}
            </Link>,
            q.category,
            q.count,
          ])}
      />
      <p className="analytics-comparison-note">
        {queryCategoryMethod} Rankings are recomputed over the complete period,
        with trimmed query text and case preserved. Filters and views are
        combined; links repeat query text only.
      </p>
      <Trend metrics={['searches', 'zeroResults']} />
      <Table
        title="Search views"
        headers={['View', 'Searches']}
        rows={data.searchViews.map((row) => [row.label, row.count])}
      />
      <Table
        title="Facet categories used"
        headers={['Category', 'Searches']}
        rows={[...facets]
          .sort((a, b) => b[1] - a[1])
          .map(([field, count]) => [
            FACET_LABELS[field] ??
              (
                { geo: 'Map bounds', year_range: 'Year range' } as Record<
                  string,
                  string
                >
              )[field] ??
              field,
            count,
          ])}
      />
      <p className="analytics-comparison-note">
        Facet counts are summed across disjoint monthly periods. A search can
        use more than one category.
      </p>
      <ZeroResultReport
        periodKey="all"
        period={`All time · ${range}`}
        searches={data.searchTotals.searches}
        zeroResults={data.searchTotals.zeroResults}
        withQuery={data.publishedMonths.reduce(
          (sum, month) =>
            sum +
            zeroSnapshots.months[month as keyof typeof zeroSnapshots.months]
              .withQuery,
          0
        )}
        queries={data.zeroQueries}
      />
    </>
  );
}

function Members() {
  const [grouping, setGrouping] = useState('code');
  const rows = (grouping === 'code' ? data.codes : data.providers).map(
    (row) => ({
      ...row,
      label:
        row.label === null
          ? 'Missing provider'
          : (memberPerformance.find(
              (member) => grouping === 'code' && member.code === row.label
            )?.name ?? row.label),
    })
  );
  return (
    <>
      <label className="analytics-query-category-filter">
        Group records by
        <select
          value={grouping}
          onChange={(event) => setGrouping(event.target.value)}
        >
          <option value="code">BTAA contribution code</option>
          <option value="provider">Provider facet</option>
        </select>
      </label>
      <section className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader title="Most viewed groups" icon={Activity} />
        <ResponsiveContainer width="100%" height={380}>
          <BarChart
            data={[...rows]
              .sort((a, b) => b.resourceViews - a.resourceViews)
              .slice(0, 10)}
            layout="vertical"
          >
            <XAxis type="number" />
            <YAxis type="category" dataKey="label" width={180} />
            <Tooltip />
            <Bar dataKey="resourceViews" name="Resource views" fill="#003c5b" />
          </BarChart>
        </ResponsiveContainer>
      </section>
      <Table
        title="Member and provider totals"
        headers={[
          'Group',
          'Catalog records',
          'Active records',
          'Views',
          'Impressions',
          'Download clicks',
          'Source clicks',
        ]}
        rows={rows.map((row) => [
          row.label,
          row.catalogRecords,
          row.activeResources,
          row.resourceViews,
          row.impressions,
          row.downloadClicks,
          row.sourceClicks,
        ])}
      />
      <p className="analytics-comparison-note">
        Counts use published, unsuppressed catalog metadata on{' '}
        {data.catalogDate}. Catalog inventory is counted once; active records
        are deduplicated across both months. Codes 01–17 identify university
        contribution streams; other and missing codes remain separate. Provider
        uses the exact named source. These totals are not sums of historical
        monthly inventory or reach.
      </p>
    </>
  );
}

export function AllTimeAnalyticsPage({
  reportId,
}: {
  reportId: AnalyticsReport;
}) {
  const [params, setParams] = useSearchParams();
  const report = analyticsReports.find((entry) => entry.id === reportId)!;
  const totals = Object.fromEntries(
    Object.keys(labels).map((key) => [
      key,
      data.daily.reduce((sum, row) => sum + row[key as DailyMetric], 0),
    ])
  );
  const download = `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify({ ...data, discoveryOutcomes: { measurementDefinitions: outcomes.measurementDefinitions, exportedAt: outcomes.exportedAt, ...outcomes.periods.all }, scope: 'All published monthly reports', clients: [...clients.values()], facets: [...facets], queryCategoryMethod, queries: data.queries.map((q) => ({ ...q, category: queryCategory(q.term) })) }, null, 2))}`;
  return (
    <div className="analytics-page min-h-screen bg-gray-50">
      <Seo
        title={`${report.label} — All time — Analytics`}
        description="Academic-year analytics across published months beginning July 1, 2026."
      />
      <AnalyticsHeader activeReport={reportId} />
      <main id="analytics-main" tabIndex={-1}>
        <div className="analytics-shell analytics-report-intro">
          <p>All time · Academic year to date</p>
          <h1>{report.label}</h1>
          <span>
            {range}. Includes published months since the academic year began
            July 1. September joins once its monthly report is published.
          </span>
          <div className="analytics-content-month">
            <label htmlFor="all-time-period">Reporting period</label>
            <select
              id="all-time-period"
              value="all"
              onChange={(event) => {
                const next = new URLSearchParams(params);
                next.set('month', event.target.value);
                setParams(next);
              }}
            >
              <option value="2026-08">August 2026</option>
              <option value="2026-07">July 2026</option>
              <option value="all">All time (since July 1)</option>
            </select>
          </div>
        </div>
        <div className="analytics-shell analytics-content analytics-all-time">
          {reportId === 'overview' && (
            <>
              <div className="analytics-client-highlights">
                {(['searches', 'views', 'downloads'] as const).map((key) => (
                  <article
                    className="analytics-panel analytics-comparison-panel"
                    key={key}
                  >
                    <h2>{labels[key]}</h2>
                    <strong>{number.format(totals[key])}</strong>
                  </article>
                ))}
              </div>
              <AccessSummary period="all" />
              <AudienceReport period="all" />
              <Trend
                metrics={[
                  'events',
                  'views',
                  'downloads',
                  'searches',
                  'requests',
                ]}
              />
            </>
          )}
          {reportId === 'discovery' && <Searches />}
          {reportId === 'members' && <Members />}
          {reportId === 'content' && (
            <>
              <AccessSummary period="all" />
              <OutlinkedResources period="all" />
              <Table
                title="Most viewed resources"
                headers={[
                  'Resource',
                  'Provider',
                  'Views',
                  'Download clicks',
                  'Source clicks',
                ]}
                rows={data.resources.map((row) => [
                  <Link to={`/resources/${encodeURIComponent(row.id)}`}>
                    {row.title ?? row.id}
                  </Link>,
                  row.provider ?? 'Missing provider',
                  row.views,
                  row.downloads,
                  row.sources,
                ])}
              />
              <Trend metrics={['views', 'downloads']} />
              <Table
                title="Most downloaded resources"
                headers={['Resource', 'Provider', 'Download clicks']}
                rows={outcomes.periods.all.downloads.map((row) => [
                  <Link to={`/resources/${encodeURIComponent(row.id)}`}>
                    {row.title ?? row.id}
                  </Link>,
                  row.provider ?? 'Missing provider',
                  row.clicks,
                ])}
              />
              <p>
                The most-viewed ranking uses current published, unsuppressed
                catalog metadata. Outlink and download rankings include all
                recorded resource IDs, retaining missing catalog records. The
                chart covers all recorded resource views and downloads.
                Collection rankings and half-month momentum remain in monthly
                reports.
              </p>
            </>
          )}
          {reportId === 'clients' && (
            <>
              <Table
                title="Clients and channels"
                headers={[
                  'Client',
                  'Channel',
                  'API requests',
                  'Searches',
                  'Interactions',
                ]}
                rows={[...clients.values()].map((row) => [
                  row.name,
                  row.channel,
                  row.requests,
                  row.searches,
                  row.events,
                ])}
              />
              <Trend metrics={['requests', 'searches', 'events']} />
              <p>
                Matching declared client/channel pairs are combined across
                monthly exports. Neither month recorded API key IDs; QGIS
                user-agent detail is unavailable for July. These cannot be
                reconstructed from rollups.
              </p>
            </>
          )}
          {reportId === 'platform' && (
            <>
              <Trend metrics={['requests', 'errors']} />
              <Table
                title="API endpoints"
                headers={['Endpoint', 'Requests', 'Server errors']}
                rows={data.endpoints.map((row) => [
                  row.label,
                  row.requests,
                  row.errors,
                ])}
              />
              <p>
                Request and error counts come from complete daily API rollups.
                All-period response-time percentiles cannot be derived by
                combining monthly percentiles; they remain available in monthly
                reports.
              </p>
            </>
          )}
          <section
            className="analytics-report-sources"
            aria-label="Sources and grouping"
          >
            <h2>Sources and grouping</h2>
            <p>
              All time begins at the academic-year start, July 1, and includes
              published monthly reports: {range} (UTC). Daily dates retain their
              month. Searches and content rankings are recomputed from
              full-period records, not combined top lists. Resource impressions
              use durable daily aggregates; inventory and attribution use the
              catalog on {data.catalogDate}.
            </p>
            <p>
              Exported{' '}
              {new Date(data.exportedAt).toLocaleDateString('en-US', {
                timeZone: 'UTC',
              })}
              . Tables are sortable and filterable; downloads contain the full
              published-period snapshot.
            </p>
            <a href={download} download="analytics-all-published-months.json">
              Download all-time snapshot (JSON)
            </a>
          </section>
        </div>
      </main>
    </div>
  );
}

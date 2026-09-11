import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { AnalyticsHeader } from './AnalyticsHeader';
import { AnalyticsTable } from './AnalyticsTable';
import { selectedAnalyticsReport } from '../../config/analyticsReports';
import { getApiBasePath } from '../../services/api';
import '../../styles/analytics.css';

type Row = Record<string, string | number | boolean | null | object>;
type Period = {
  id: string;
  revision: string;
  complete: boolean;
  start: string;
  endExclusive: string;
};
export type ReportingManifest = {
  stale?: boolean;
  schemaVersion: 1;
  latest: string | null;
  periods: Period[];
  throughExclusive: string;
};
export type RuntimeReport = {
  comparison: Row[];
  collections: Row[];
  discoveryViews: Row[];
  memberResources: Row[];
  memberDaily: Row[];
  zeroCategories: Row[];
  schemaVersion: 1;
  revision: string;
  period: string;
  start: string;
  endExclusive: string;
  complete: boolean;
  coverage: Row[];
  sourceCoverage: Record<string, boolean>;
  missingMonths: string[];
  sources: Record<string, string>;
  totals: Record<string, number | null>;
  daily: Row[];
  queries: Row[];
  zeroQueries: Row[];
  resources: Row[];
  members: Row[];
  clients: Row[];
  endpoints: Row[];
  facets: Row[];
  categories: Row[];
  zeroResultPercent: number | null;
  trackedVisits: { value: number | null; status: string; definition: string };
  latency: { meanMs: number | null; p95Ms: number | null };
};
const colors = ['#2563eb', '#047857', '#854d0e', '#7c3aed', '#be123c'];
const display = (value: Row[string]) =>
  value == null
    ? 'Unavailable'
    : typeof value === 'object'
      ? JSON.stringify(value)
      : String(value);
const title = (key: string) =>
  key.replace(/([A-Z])/g, ' $1').replace(/^./, (s) => s.toUpperCase());

function DataTable({
  name,
  rows,
  columns,
  report,
  table,
}: {
  name: string;
  rows: Row[];
  columns: string[];
  report: RuntimeReport;
  table: string;
}) {
  const download = `${getApiBasePath()}/analytics/reports/${report.period}/${report.revision}/download/${table}`;
  return (
    <section className="analytics-panel analytics-runtime-panel">
      <h2>{name}</h2>
      <p>
        <a href={`${download}?format=csv`}>Download CSV</a> ·{' '}
        <a href={`${download}?format=json`}>Download JSON</a>
      </p>
      <AnalyticsTable label={name}>
        <thead>
          <tr>
            {columns.map((key) => (
              <th key={key}>{title(key)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((key) => (
                <td
                  key={key}
                  data-sort-value={
                    typeof row[key] === 'number'
                      ? (row[key] as number)
                      : undefined
                  }
                >
                  {key === 'id' ? (
                    <a
                      href={`/resources/${encodeURIComponent(String(row[key]))}`}
                    >
                      {display(row[key])}
                    </a>
                  ) : (
                    display(row[key])
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </AnalyticsTable>
      {!rows.length && <p>No recorded rows for this period.</p>}
    </section>
  );
}

export function RuntimeReportView({
  report,
  active,
}: {
  report: RuntimeReport;
  active: string;
}) {
  const [grouping, setGrouping] = useState('provider');
  const [category, setCategory] = useState('all');
  const [member, setMember] = useState('all');
  const table = (
    name: string,
    key: keyof RuntimeReport,
    columns: string[],
    rows?: Row[]
  ) => (
    <DataTable
      name={name}
      rows={rows ?? (report[key] as Row[])}
      columns={columns}
      report={report}
      table={key}
    />
  );
  return (
    <>
      {!report.complete && (
        <p role="status">
          This period has incomplete historical coverage. Values represent
          preserved evidence only. Missing months:{' '}
          {report.missingMonths.join(', ') || 'see source coverage'}. Tracked
          visits are estimates only when the required sources are complete.
        </p>
      )}
      <p>{report.sources[active]}</p>
      <details>
        <summary>Data sources and coverage</summary>
        <ul>
          {Object.entries(report.sourceCoverage).map(([source, complete]) => (
            <li key={source}>
              {source}:{' '}
              {complete
                ? 'Complete preserved evidence'
                : 'Incomplete historical evidence'}
            </li>
          ))}
        </ul>
        {report.coverage.map((row) => (
          <p key={String(row.month)}>
            {String(row.month)} — catalog captured{' '}
            {display(row.catalogCapturedAt)}.
          </p>
        ))}
      </details>
      {active === 'overview' && (
        <>
          <dl className="analytics-runtime-totals">
            {Object.entries(report.totals)
              .filter(([key]) => !key.startsWith('duration'))
              .map(([key, value]) => (
                <div key={key}>
                  <dt>{title(key)}</dt>
                  <dd>
                    {value == null ? 'Unavailable' : value.toLocaleString()}
                  </dd>
                </div>
              ))}
          </dl>
          <p>
            Tracked visits:{' '}
            {report.trackedVisits.value == null
              ? 'Unavailable'
              : `approximately ${report.trackedVisits.value.toLocaleString()}`}
            . {report.trackedVisits.definition}
          </p>
          <h2>Daily totals</h2>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={report.daily}>
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Legend />
              {['views', 'searches', 'downloads'].map((key, i) => (
                <Line
                  key={key}
                  type="linear"
                  dataKey={key}
                  stroke={colors[i]}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
          {table('Daily totals', 'daily', [
            'date',
            'requests',
            'views',
            'searches',
            'downloads',
          ])}
        </>
      )}
      {active === 'comparison' && (
        <>
          <h2>Monthly totals</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={report.comparison}>
              <XAxis dataKey="month" />
              <YAxis />
              <Tooltip />
              <Legend />
              {['views', 'searches', 'downloads'].map((key, i) => (
                <Bar key={key} dataKey={key} fill={colors[i]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
          {table('Month comparison', 'comparison', [
            'month',
            'complete',
            'requests',
            'views',
            'searches',
            'downloads',
          ])}
        </>
      )}
      {active === 'discovery' && (
        <>
          <label>
            Query category{' '}
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="all">All categories</option>
              {report.categories.map((row) => (
                <option key={String(row.category)} value={String(row.category)}>
                  {String(row.category)}
                </option>
              ))}
            </select>
          </label>
          {table(
            'Top 50 searches',
            'queries',
            ['query', 'category', 'count', 'zeroResults'],
            report.queries
              .filter((r) => category === 'all' || r.category === category)
              .slice(0, 50)
          )}
          <h2>Query categories</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={report.categories}
                dataKey="count"
                nameKey="category"
                label
              >
                {report.categories.map((_, i) => (
                  <Cell key={i} fill={colors[i % colors.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
          <h2>Zero-result query categories</h2>
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie
                data={report.zeroCategories}
                dataKey="count"
                nameKey="category"
                label
              >
                {report.zeroCategories.map((_, i) => (
                  <Cell key={i} fill={colors[i % colors.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
          <h2>Facet use</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={report.facets}>
              <XAxis dataKey="facet" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill={colors[0]} />
            </BarChart>
          </ResponsiveContainer>
          {table('Facet categories', 'facets', ['facet', 'count'])}
          <p>
            Searches without results:{' '}
            {report.zeroResultPercent == null
              ? 'Unavailable'
              : `${report.zeroResultPercent.toFixed(1)}%`}
            .
          </p>
          {table('Zero-result queries', 'zeroQueries', [
            'query',
            'category',
            'count',
            'context',
          ])}
        </>
      )}
      {active === 'content' &&
        table('Popular content', 'resources', [
          'id',
          'title',
          'views',
          'downloads',
          'sourceClicks',
          'impressions',
        ])}
      {active === 'content' &&
        table('Collections', 'collections', [
          'id',
          'title',
          'views',
          'downloads',
          'impressions',
        ])}
      {active === 'discovery' &&
        table('Search views', 'discoveryViews', ['view', 'count'])}
      {active === 'members' && (
        <>
          <label>
            Group content by{' '}
            <select
              value={grouping}
              onChange={(e) => {
                setGrouping(e.target.value);
                setMember('all');
              }}
            >
              <option value="provider">Provider</option>
              <option value="code">Contribution code</option>
            </select>
          </label>
          {table(
            'Members',
            'members',
            [
              'name',
              'inventory',
              'activeResources',
              'views',
              'downloads',
              'impressions',
            ],
            report.members.filter((r) => r.grouping === grouping)
          )}
        </>
      )}
      {active === 'members' && (
        <>
          <label>
            Campus or provider{' '}
            <select value={member} onChange={(e) => setMember(e.target.value)}>
              <option value="all">All groups</option>
              {report.members
                .filter((r) => r.grouping === grouping)
                .map((r) => (
                  <option key={String(r.name)} value={String(r.name)}>
                    {String(r.name)}
                  </option>
                ))}
            </select>
          </label>
          {member !== 'all' && (
            <>
              <h2>{member}</h2>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart
                  data={report.memberDaily.filter(
                    (r) => r.grouping === grouping && r.name === member
                  )}
                >
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line
                    type="linear"
                    dataKey="views"
                    stroke={colors[0]}
                    dot={false}
                  />
                  <Line
                    type="linear"
                    dataKey="downloads"
                    stroke={colors[1]}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
              {table(
                'Leading member content',
                'memberResources',
                ['id', 'title', 'views', 'downloads', 'sourceClicks'],
                report.memberResources.filter(
                  (r) => r.grouping === grouping && r.name === member
                )
              )}
            </>
          )}
        </>
      )}
      {active === 'clients' && (
        <p>
          Requests with a QGIS user-agent signal:{' '}
          {report.totals.qgisUserAgentRequests == null
            ? 'Unavailable'
            : report.totals.qgisUserAgentRequests.toLocaleString()}
          . This is a reported client signal, not verified identity.
        </p>
      )}
      {active === 'clients' &&
        table('Clients and API keys', 'clients', [
          'client',
          'channel',
          'apiKey',
          'requests',
          'searches',
          'events',
        ])}
      {active === 'platform' && (
        <>
          <p>
            Mean response time:{' '}
            {report.latency.meanMs?.toFixed(1) ?? 'Unavailable'} ms. 95th
            percentile: {report.latency.p95Ms ?? 'Unavailable'} ms.
          </p>
          {table('API reliability', 'endpoints', [
            'endpoint',
            'method',
            'status',
            'count',
          ])}
        </>
      )}
    </>
  );
}

export function RuntimeAnalyticsPage() {
  const [params, setParams] = useSearchParams();
  const [manifest, setManifest] = useState<ReportingManifest | null>(null);
  const [report, setReport] = useState<RuntimeReport | null>(null);
  const [error, setError] = useState('');
  const active = selectedAnalyticsReport(params).id;
  const requested = params.get('month');
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${getApiBasePath()}/analytics/reports/manifest`, {
      signal: controller.signal,
    })
      .then((r) => {
        if (!r.ok) throw new Error('Runtime reports are not available yet.');
        return r.json();
      })
      .then((data: ReportingManifest) => {
        if (data.schemaVersion !== 1)
          throw new Error('Unsupported report version.');
        setManifest(data);
      })
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message);
      });
    return () => controller.abort();
  }, []);
  const selected = requested ?? manifest?.latest;
  useEffect(() => {
    if (!manifest) return;
    const entry = manifest.periods.find((p) => p.id === selected);
    setReport(null);
    if (!entry) {
      setError('This period is unavailable. Choose a published period.');
      return;
    }
    setError('');
    const controller = new AbortController();
    fetch(
      `${getApiBasePath()}/analytics/reports/${entry.id}/${entry.revision}`,
      { signal: controller.signal }
    )
      .then((r) => {
        if (!r.ok) throw new Error('Could not load this report.');
        return r.json();
      })
      .then((data: RuntimeReport) => {
        if (data.schemaVersion !== 1 || data.revision !== entry.revision)
          throw new Error('Report version mismatch.');
        setReport(data);
      })
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message);
      });
    return () => controller.abort();
  }, [manifest, selected]);
  return (
    <div className="analytics-page">
      <AnalyticsHeader activeReport={active} />
      <main id="analytics-main" className="analytics-shell">
        <h1>{selectedAnalyticsReport(params).label}</h1>
        {manifest && (
          <label>
            Reporting period{' '}
            <select
              value={selected ?? ''}
              onChange={(e) => {
                const next = new URLSearchParams(params);
                next.set('month', e.target.value);
                setParams(next);
              }}
            >
              <option value="" disabled>
                Choose a period
              </option>
              {manifest.periods.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.id === 'all' ? 'All time since July 2026' : p.id}
                  {p.complete ? '' : ' (incomplete)'}
                </option>
              ))}
            </select>
          </label>
        )}
        {manifest?.stale && (
          <p role="status">
            The latest publication is overdue. The previous complete reports
            remain available.
          </p>
        )}
        {error && <p role="alert">{error}</p>}
        {!error && !report && <p role="status">Loading report…</p>}
        {report && (
          <>
            <p>
              {report.start} through {report.endExclusive} (end exclusive, UTC)
            </p>
            <RuntimeReportView report={report} active={active} />
            <p>Report revision {report.revision.slice(0, 12)}</p>
          </>
        )}
      </main>
    </div>
  );
}

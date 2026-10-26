import { useId, useState, type ReactNode } from 'react';
import { useSearchParams } from 'react-router';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AnalyticsHeader } from './AnalyticsHeader';
import { useAnalyticsData } from './AnalyticsData';
import { chartTheme } from './chartTheme';
import { Footer } from '../layout/Footer';
import { Seo } from '../Seo';
import {
  buildAnalyticsSummary,
  type ResourceAccessPattern,
  summaryDate,
} from '../../utils/analyticsSummary';
import '../../styles/analytics.css';
import {
  latestMonth,
  selectedSummaryPeriod,
} from '../../config/analyticsPeriods';
import { ReportingPeriodPicker } from './ReportingPeriodPicker';

const number = new Intl.NumberFormat('en-US');
const compact = new Intl.NumberFormat('en-US', { notation: 'compact' });
const signed = new Intl.NumberFormat('en-US', { signDisplay: 'exceptZero' });
const percent = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 2,
  signDisplay: 'exceptZero',
});
const ratio = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 });
const display = (value: number | null) =>
  value === null ? 'Unavailable' : number.format(value);
const shortDate = (day: string) =>
  new Date(`${day}T00:00:00Z`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });

type RankedItem = { id: string; title: string; clicks: number };

function ExpandableRanking({
  label,
  className,
  children,
}: {
  label: string;
  className: string;
  children: ReactNode[];
}) {
  const [expanded, setExpanded] = useState(false);
  const id = useId();
  return (
    <>
      <ol id={id} className={className}>
        {expanded ? children : children.slice(0, 5)}
      </ol>
      {children.length > 5 && (
        <button
          type="button"
          className="analytics-summary-expand"
          aria-controls={id}
          aria-expanded={expanded}
          aria-label={
            expanded
              ? `Show fewer ${label.toLowerCase()}`
              : `Show all ${children.length} ${label.toLowerCase()}`
          }
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? 'Show fewer' : `Show all ${children.length}`}
        </button>
      )}
    </>
  );
}

function ResourceRanking({
  title,
  rows,
}: {
  title: string;
  rows: RankedItem[] | null;
}) {
  const top = rows
    ?.slice()
    .sort((a, b) => b.clicks - a.clicks || a.id.localeCompare(b.id))
    .slice(0, 20);
  const maximum = Math.max(1, ...(top?.map((row) => row.clicks) ?? []));
  return (
    <article className="analytics-panel analytics-summary-card">
      <h3>{title}</h3>
      {!top ? (
        <p className="analytics-summary-empty">
          Rankings unavailable for this period
        </p>
      ) : top.length === 0 ? (
        <p className="analytics-summary-empty">No recorded clicks</p>
      ) : (
        <ExpandableRanking label={title} className="analytics-summary-ranking">
          {top.map((row) => (
            <li key={row.id}>
              <div>
                <a href={`/resources/${encodeURIComponent(row.id)}`}>
                  {row.title || row.id}
                </a>
                <strong>
                  {number.format(row.clicks)}
                  <span className="sr-only"> clicks</span>
                </strong>
              </div>
              <div className="analytics-summary-bar" aria-hidden="true">
                <span style={{ width: `${(row.clicks / maximum) * 100}%` }} />
              </div>
            </li>
          ))}
        </ExpandableRanking>
      )}
    </article>
  );
}

function TermRanking({
  title,
  rows,
}: {
  title: string;
  rows: { term: string; count: number }[] | null;
}) {
  return (
    <article className="analytics-panel analytics-summary-card">
      <h3>{title}</h3>
      {!rows ? (
        <p className="analytics-summary-empty">
          Rankings unavailable for this period
        </p>
      ) : rows.length === 0 ? (
        <p className="analytics-summary-empty">No recorded searches</p>
      ) : (
        <ExpandableRanking label={title} className="analytics-summary-terms">
          {rows
            .slice()
            .sort((a, b) => b.count - a.count || a.term.localeCompare(b.term))
            .slice(0, 20)
            .map((row) => (
              <li key={row.term}>
                <span>{row.term}</span>
                <strong>
                  {number.format(row.count)}
                  <span className="sr-only"> searches</span>
                </strong>
              </li>
            ))}
        </ExpandableRanking>
      )}
    </article>
  );
}

function RecordAccessList({
  title,
  rows,
}: {
  title: string;
  rows: ResourceAccessPattern[];
}) {
  return (
    <article className="analytics-panel analytics-summary-card">
      <h3>{title}</h3>
      {rows.length ? (
        <ol className="analytics-summary-access-patterns">
          {rows.map((row) => (
            <li key={row.id}>
              <a href={`/resources/${encodeURIComponent(row.id)}`}>
                {row.title || row.id}
              </a>
              <dl>
                <div>
                  <dt>Views</dt>
                  <dd>{number.format(row.views)}</dd>
                </div>
                <div>
                  <dt>Access clicks</dt>
                  <dd>{number.format(row.clicks)}</dd>
                </div>
                <div>
                  <dt>Clicks / 100 views</dt>
                  <dd>{ratio.format(row.clicksPer100Views)}</dd>
                </div>
              </dl>
              <p>
                {number.format(row.sources)} outlink clicks ·{' '}
                {number.format(row.downloads)} download clicks
              </p>
            </li>
          ))}
        </ol>
      ) : (
        <p className="analytics-summary-empty">
          No records meet the sample criteria.
        </p>
      )}
    </article>
  );
}

function DiscoveryChart({
  metric,
  data,
}: {
  metric: 'visits' | 'searches';
  data: ReturnType<typeof buildAnalyticsSummary>;
}) {
  const title = metric === 'visits' ? 'Visits' : 'Searches';
  const note =
    metric === 'searches'
      ? 'Includes filters and results-page changes'
      : data.estimatedVisits
        ? 'Estimated · tracked browser-tab visits'
        : 'Tracked browser-tab visits';
  const range = `${summaryDate(data.window.start)} – ${summaryDate(data.window.end)}`;
  return (
    <article className="analytics-panel analytics-summary-card">
      <h3>{title}</h3>
      <strong className="analytics-summary-total">
        {display(data[metric])}
      </strong>
      {data.dailyComplete ? (
        <>
          <p className="analytics-summary-caption">{note}</p>
          <div
            className="analytics-summary-chart"
            role="img"
            aria-label={`Daily ${title.toLowerCase()}, ${range}${metric === 'visits' && data.estimatedVisits ? ', estimated' : ''}`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data.daily}
                margin={{ top: 12, right: 12, left: 0, bottom: 0 }}
                accessibilityLayer
              >
                <CartesianGrid {...chartTheme.grid} />
                <XAxis
                  dataKey="day"
                  tickFormatter={shortDate}
                  tick={chartTheme.tick}
                  minTickGap={45}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tickFormatter={(value: number) => compact.format(value)}
                  tick={chartTheme.tick}
                  width={45}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  labelFormatter={(label) => shortDate(String(label))}
                  formatter={(value) => [number.format(Number(value)), title]}
                  contentStyle={chartTheme.tooltip}
                />
                <Line
                  dataKey={metric}
                  name={title}
                  {...chartTheme.series}
                  type="monotone"
                  dot={false}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <details className="analytics-summary-data">
            <summary>Daily values</summary>
            <div>
              <table>
                <caption className="sr-only">
                  Daily {title.toLowerCase()}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col">{title}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.daily.map((row) => (
                    <tr key={row.day}>
                      <th scope="row">{shortDate(row.day)}</th>
                      <td>{number.format(row[metric])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      ) : (
        <p className="analytics-summary-empty">
          Daily activity is unavailable for this period.
        </p>
      )}
    </article>
  );
}

export function SummaryAnalyticsPage() {
  const analytics = useAnalyticsData();
  const [params, setParams] = useSearchParams();
  const period = selectedSummaryPeriod(params.get('month'));
  const selection =
    period === 'all' ? 'all' : period === '3months' ? '3months' : 'month';
  const data = buildAnalyticsSummary(
    analytics,
    selection === 'month' ? period : latestMonth,
    selection
  );
  return (
    <div className="analytics-page analytics-summary-page min-h-screen bg-gray-50">
      <Seo
        title="Summary — Analytics"
        description="Geoportal searches, discovery trends, and resource access at a glance."
      />
      <AnalyticsHeader activeReport="summary" />
      <main id="analytics-main" tabIndex={-1}>
        <div className="analytics-shell analytics-summary-period">
          <h1 className="sr-only">Summary</h1>
          <ReportingPeriodPicker
            id="summary-period"
            label="Reporting period"
            value={period}
            includeThreeMonths
            onChange={(value) => {
              const next = new URLSearchParams(params);
              next.set('month', value);
              setParams(next, { preventScrollReset: true });
            }}
          />
        </div>
        <div className="analytics-shell analytics-summary-content">
          <section aria-labelledby="summary-discovery">
            <div className="analytics-summary-section-heading">
              <h2 id="summary-discovery">Discovery activity</h2>
            </div>
            <div className="analytics-summary-grid">
              {(['visits', 'searches'] as const).map((metric) => (
                <DiscoveryChart key={metric} metric={metric} data={data} />
              ))}
            </div>
          </section>
          <section aria-labelledby="summary-terms">
            <div className="analytics-summary-section-heading">
              <h2 id="summary-terms">Top search terms</h2>
            </div>
            <div className="analytics-summary-grid">
              <TermRanking
                key={`${period}-common`}
                title="Most common"
                rows={data.queries}
              />
              <TermRanking
                key={`${period}-no-results`}
                title="No-result searches"
                rows={data.zeroQueries}
              />
            </div>
          </section>
          <section aria-labelledby="summary-access">
            <div className="analytics-summary-section-heading">
              <h2 id="summary-access">Successful access</h2>
            </div>
            <div className="analytics-summary-grid">
              {(['sources', 'downloads'] as const).map((key) => {
                const maximum = Math.max(
                  1,
                  ...data.monthly.map((row) => row[key] ?? 0)
                );
                return (
                  <article
                    className="analytics-panel analytics-summary-card"
                    key={key}
                  >
                    <h3>{key === 'sources' ? 'Outlinks' : 'Downloads'}</h3>
                    <strong className="analytics-summary-total">
                      {display(data[key])}
                    </strong>
                    <ul
                      className={
                        key === 'downloads'
                          ? 'analytics-summary-months analytics-summary-months--downloads'
                          : 'analytics-summary-months'
                      }
                    >
                      {data.monthly.map((row) => (
                        <li key={row.period}>
                          <div>
                            <span>{row.label}</span>
                            <strong>{display(row[key])}</strong>
                          </div>
                          {row[key] !== null && (
                            <div
                              className="analytics-summary-bar"
                              aria-hidden="true"
                            >
                              <span
                                style={{
                                  width: `${(row[key] / maximum) * 100}%`,
                                }}
                              />
                            </div>
                          )}
                        </li>
                      ))}
                    </ul>
                  </article>
                );
              })}
            </div>
          </section>
          <section aria-labelledby="summary-resources">
            <div className="analytics-summary-section-heading">
              <h2 id="summary-resources">High-value resources</h2>
            </div>
            <div className="analytics-summary-grid">
              <ResourceRanking
                key={`${period}-outlinks`}
                title="Top outlinked resources"
                rows={data.outlinks}
              />
              <ResourceRanking
                key={`${period}-downloads`}
                title="Top downloaded resources"
                rows={data.topDownloads}
              />
            </div>
          </section>
          <section aria-labelledby="summary-record-access">
            <div className="analytics-summary-section-heading">
              <h2 id="summary-record-access">Record access patterns</h2>
              <span className="analytics-summary-caption">Experimental</span>
            </div>
            {data.recordAccessPatterns ? (
              <>
                <div className="analytics-summary-grid">
                  <RecordAccessList
                    title="Fewer access clicks per view"
                    rows={data.recordAccessPatterns.fewerClicks}
                  />
                  <RecordAccessList
                    title="More access clicks per view"
                    rows={data.recordAccessPatterns.moreClicks}
                  />
                </div>
                <p className="analytics-summary-caption analytics-summary-catalog-note">
                  Sample of published leading records with at least 20 views.
                  Access clicks combine outlinks and downloads; repeated clicks
                  count separately. Ratios are not visit success rates.
                </p>
              </>
            ) : (
              <div className="analytics-panel analytics-summary-card">
                <p className="analytics-summary-caption">
                  Combined views and access-click counts are unavailable for
                  this period. Select All time to see the saved sample.
                </p>
              </div>
            )}
          </section>
          <section aria-labelledby="summary-growth">
            <div className="analytics-summary-section-heading">
              <h2 id="summary-growth">Collection growth</h2>
            </div>
            <div className="analytics-summary-grid">
              <article className="analytics-panel analytics-summary-card">
                <h3>Published resources</h3>
                <strong className="analytics-summary-total">
                  {display(data.catalog?.total ?? null)}
                </strong>
                <p className="analytics-summary-caption">
                  {data.catalog
                    ? `As of ${summaryDate(data.catalog.date)}`
                    : 'No catalog snapshot available'}
                </p>
              </article>
              <article className="analytics-panel analytics-summary-card">
                <h3>Net change</h3>
                <strong className="analytics-summary-total">
                  {data.catalog?.change != null
                    ? signed.format(data.catalog.change)
                    : 'Unavailable'}
                </strong>
                <p className="analytics-summary-caption">
                  {data.catalog?.previousDate ? (
                    <>
                      {data.catalog.percentChange !== null &&
                        `${percent.format(data.catalog.percentChange)}% · `}
                      Since {summaryDate(data.catalog.previousDate)} ·{' '}
                      {display(data.catalog.previousTotal)} resources
                    </>
                  ) : (
                    'No earlier catalog snapshot available'
                  )}
                </p>
              </article>
            </div>
            <p className="analytics-summary-caption analytics-summary-catalog-note">
              Net change includes additions, removals, and publication changes.
            </p>
          </section>
        </div>
      </main>
      <Footer />
    </div>
  );
}

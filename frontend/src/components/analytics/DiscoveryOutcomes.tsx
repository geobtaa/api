import { useState } from 'react';
import { Link } from 'react-router';
import { ExternalLink, Users } from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  outcomes,
  outcomeLabels,
  type OutcomePeriod,
} from '../../data/analytics/outcomes';
import { AnalyticsTable } from './AnalyticsTable';
import { ReportPanelHeader } from './ReportPanelHeader';
const n = new Intl.NumberFormat('en-US');
const dateLabel = (day: string) =>
  new Date(day + 'T00:00:00Z').toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });

export function AccessSummary({ period }: { period: OutcomePeriod }) {
  const report = outcomes.periods[period];
  const months =
    period === 'all' ? (['2026-07', '2026-08'] as const) : [period];
  const maximum = Math.max(
    ...months.flatMap((month) => [
      outcomes.periods[month].totals.sources,
      outcomes.periods[month].totals.downloads,
    ])
  );
  return (
    <section
      className="analytics-panel analytics-outcomes"
      aria-label="Successful access"
    >
      <ReportPanelHeader
        title="Successful access"
        icon={ExternalLink}
        level={2}
      />
      <div className="analytics-outcomes-body">
        <div className="analytics-outcome-totals">
          <p>
            <strong>{n.format(report.totals.sources)}</strong>Source-site clicks
          </p>
          <p>
            <strong>{n.format(report.totals.downloads)}</strong>Download clicks
          </p>
        </div>
        <figure
          aria-label={`Monthly access totals for ${outcomeLabels[period]}`}
        >
          {months.map((month) => (
            <div className="analytics-access-month" key={month}>
              <h3>{outcomeLabels[month]}</h3>
              {(['sources', 'downloads'] as const).map((metric) => (
                <div className="analytics-access-bar" key={metric}>
                  <span>
                    {metric === 'sources'
                      ? 'Source-site clicks'
                      : 'Download clicks'}
                  </span>
                  <div aria-hidden="true">
                    <i
                      className={metric}
                      style={{
                        width: `${(outcomes.periods[month].totals[metric] / maximum) * 100}%`,
                      }}
                    />
                  </div>
                  <strong>
                    {n.format(outcomes.periods[month].totals[metric])}
                  </strong>
                </div>
              ))}
            </div>
          ))}
          <figcaption>
            Source-site clicks record visits to the authoritative source link.
            Downloads record link clicks, not verified file transfers. Counts
            cover all recorded resource IDs, including records absent from the
            current catalog.
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

export function OutlinkedResources({ period }: { period: OutcomePeriod }) {
  const report = outcomes.periods[period];
  return (
    <section className="analytics-panel analytics-outcomes">
      <ReportPanelHeader
        title="Most outlinked resources"
        icon={ExternalLink}
        level={2}
      />
      <div className="analytics-outcomes-body">
        <p>
          Top 50 resources ranked independently by source-site clicks in{' '}
          {outcomeLabels[period]}. Catalog labels are from{' '}
          {outcomes.catalogDate}; missing records remain in the ranking.
        </p>
        <div className="analytics-comparison-scroll">
          <AnalyticsTable className="analytics-comparison-table analytics-outlinks-table">
            <caption className="sr-only">
              {outcomeLabels[period]} most outlinked resources
            </caption>
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">Resource</th>
                <th scope="col">Provider</th>
                <th scope="col">Source-site clicks</th>
              </tr>
            </thead>
            <tbody>
              {report.outlinks.map((row, i) => (
                <tr key={row.id ?? 'missing'}>
                  <td>{i + 1}</td>
                  <th scope="row">
                    {row.id ? (
                      <Link to={`/resources/${encodeURIComponent(row.id)}`}>
                        {row.title}
                      </Link>
                    ) : (
                      row.title
                    )}
                  </th>
                  <td>{row.provider || 'Unavailable'}</td>
                  <td>{n.format(row.clicks)}</td>
                </tr>
              ))}
            </tbody>
          </AnalyticsTable>
        </div>
        <p className="analytics-comparison-note">
          This list is selected by source-site clicks, independently of the
          most-viewed list. Homepage visits and unrelated outbound-link events
          are excluded.
        </p>
      </div>
    </section>
  );
}

export function AudienceReport({ period }: { period: OutcomePeriod }) {
  const report = outcomes.periods[period];
  const [metric, setMetric] = useState<'visits' | 'searches' | 'views'>(
    'visits'
  );
  const labels = {
    visits: 'Tracked visits',
    searches: 'Search result pages',
    views: 'Resource views',
  };
  return (
    <section
      className="analytics-panel analytics-outcomes"
      aria-label="Audience and discovery coverage"
    >
      <ReportPanelHeader
        title="Audience and discovery"
        icon={Users}
        level={2}
      />
      <div className="analytics-outcomes-body">
        <div className="analytics-audience-cards">
          <div>
            <h3>Tracked visits</h3>
            <strong>{n.format(report.audience.trackedVisits)}</strong>
            <p>
              Distinct tab-scoped visit tokens across searches and interactions.
            </p>
          </div>
          <div>
            <h3>Unique visitors</h3>
            <strong>Unavailable</strong>
            <p>
              No persistent visitor identifier is recorded. Tab tokens cannot
              identify unique people.
            </p>
          </div>
          <div>
            <h3>All pageviews</h3>
            <strong>Unavailable</strong>
            <p>
              General page-view events were not recorded in these monthly
              datasets. Resource views cover detail pages only.
            </p>
          </div>
        </div>
        <label className="analytics-query-category-filter">
          Audience chart metric
          <select
            value={metric}
            onChange={(e) => setMetric(e.target.value as typeof metric)}
          >
            {Object.entries(labels).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <div
          role="img"
          aria-label={`${labels[metric]} by UTC day in ${outcomeLabels[period]}; exact values follow`}
        >
          <ResponsiveContainer width="100%" height={270}>
            <LineChart data={report.daily}>
              <CartesianGrid strokeDasharray="2 6" />
              <XAxis dataKey="day" tickFormatter={dateLabel} minTickGap={35} />
              <YAxis />
              <Tooltip labelFormatter={(v) => dateLabel(String(v))} />
              <Line
                type="linear"
                dataKey={metric}
                name={labels[metric]}
                stroke="#003c5b"
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <details>
          <summary>Daily audience values</summary>
          <div className="analytics-comparison-scroll">
            <AnalyticsTable className="analytics-comparison-table">
              <caption>{outcomeLabels[period]} audience daily values</caption>
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Tracked visits</th>
                  <th scope="col">Search result pages</th>
                  <th scope="col">Resource views</th>
                </tr>
              </thead>
              <tbody>
                {report.daily.map((row) => (
                  <tr key={row.day}>
                    <th scope="row">{row.day}</th>
                    <td>{n.format(row.visits)}</td>
                    <td>{n.format(row.searches)}</td>
                    <td>{n.format(row.views)}</td>
                  </tr>
                ))}
              </tbody>
            </AnalyticsTable>
          </div>
        </details>
        <p className="analytics-comparison-note">
          All {n.format(report.audience.activityRecords)} search and interaction
          records declare the Geoportal browser client.{' '}
          {n.format(report.audience.recordsWithoutToken)} records lack a visit
          token and cannot contribute to tracked visits. Tokens use
          sessionStorage: a tab can span days, and multiple tabs can represent
          one person. Daily distinct counts must not be summed to obtain period
          visits. These are not GA4 sessions or engaged-visit totals. Searches
          count rendered result pages, including pagination and filter changes,
          not only new typed queries.
        </p>
        <p className="analytics-comparison-note">
          Source: analytics_searches and analytics_events, exported{' '}
          {outcomes.catalogDate}, UTC. Historical values are complete for these
          recorded event types, not a census of every visitor. The GA4/GTM
          connection and general SPA pageview coverage remain unverified.
        </p>
        <a
          href={`data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify({ measurementDefinitions: outcomes.measurementDefinitions, exportedAt: outcomes.exportedAt, catalogDate: outcomes.catalogDate, period, ...report }, null, 2))}`}
          download={`analytics-discovery-outcomes-${period}.json`}
        >
          Download access, audience, and search-context data (JSON)
        </a>
      </div>
    </section>
  );
}

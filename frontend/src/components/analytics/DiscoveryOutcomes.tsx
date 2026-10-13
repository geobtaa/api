import { useAnalyticsData } from './AnalyticsData';

import { RankingRow } from './RankingRow';
import { useRanking } from './useRanking';
import { MetricHeading } from './MetricHeading';
import { ResourceThumbnail } from './ResourceThumbnail';
import { useState } from 'react';
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
import type { OutcomePeriod } from '../../data/analytics/outcomes';
import { AnalyticsTable } from './AnalyticsTable';
import { ReportPanelHeader } from './ReportPanelHeader';
const n = new Intl.NumberFormat('en-US');
const dateLabel = (day: string) =>
  new Date(day + 'T00:00:00Z').toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });

export function OutlinkedResources({ period }: { period: OutcomePeriod }) {
  const analytics = useAnalyticsData();
  const previousRankingValue =
    analytics['popularMomentum'].previousRankingValue;
  const outcomes = analytics['outcomes'].outcomes;
  const outcomeLabels = analytics['outcomes'].outcomeLabels;

  const report = outcomes.periods[period];
  const ranking = useRanking(
    report.outlinks.map((row) => ({
      ...row,
      provider: row.provider || 'Unavailable',
    })),
    (row) => row.clicks,
    'Resources with the most source-site clicks'
  );
  const maximum = Math.max(1, ...report.outlinks.map((row) => row.clicks));
  return (
    <section
      id="outlinked-resources"
      className="analytics-panel analytics-outcomes"
    >
      <ReportPanelHeader
        title="Resources with the most source-site clicks"
        icon={ExternalLink}
        level={2}
      />
      <div className="analytics-outcomes-body">
        <p>
          Top 50 resources ranked independently by source-site clicks in{' '}
          {outcomeLabels[period]}. Catalog labels are from{' '}
          {new Date(outcomes.contentCatalogCapturedAt).toLocaleDateString(
            'en-US',
            {
              month: 'long',
              day: 'numeric',
              year: 'numeric',
              timeZone: 'UTC',
            }
          )}
          ; missing records remain in the ranking.
        </p>
      </div>
      {ranking.controls}
      <div className="analytics-ranking-list">
        {ranking.visible.map(({ row, rank }) => (
          <RankingRow
            key={row.id ?? 'missing'}
            rank={rank}
            title={row.title}
            href={
              row.id ? `/resources/${encodeURIComponent(row.id)}` : undefined
            }
            thumbnail={
              row.id ? (
                <ResourceThumbnail
                  resource={{ id: row.id, title: row.title }}
                  eager={rank === 1}
                />
              ) : undefined
            }
            description={row.provider}
            value={row.clicks}
            label="source-site clicks"
            maximum={maximum}
            previousValue={previousRankingValue(period, 'outlinks', row.id)}
          />
        ))}
      </div>
      <div className="analytics-outcomes-body">
        <p className="analytics-comparison-note">
          This list is selected by source-site clicks, independently of the
          most-viewed list. Homepage visits and unrelated outbound-link events
          are excluded.
        </p>
      </div>
    </section>
  );
}

export function AudienceReport({
  period,
  embedded = false,
}: {
  period: OutcomePeriod;
  embedded?: boolean;
}) {
  const analytics = useAnalyticsData();
  const outcomes = analytics['outcomes'].outcomes;
  const visitsAreEstimated = analytics['outcomes'].visitsAreEstimated;
  const outcomeLabels = analytics['outcomes'].outcomeLabels;

  const report = outcomes.periods[period];
  const [metric, setMetric] = useState<'visits' | 'searches' | 'views'>(
    'visits'
  );
  const labels = {
    visits: visitsAreEstimated(period)
      ? 'Tracked visits (estimated)'
      : 'Tracked visits',
    searches: 'Search result pages',
    views: 'Resource views',
  };
  const Container = embedded ? 'div' : 'section';
  return (
    <Container
      className={
        embedded ? 'analytics-outcomes' : 'analytics-panel analytics-outcomes'
      }
      aria-label="Audience and discovery coverage"
    >
      {!embedded && (
        <ReportPanelHeader
          title="Audience and discovery"
          icon={Users}
          level={2}
        />
      )}
      <div className="analytics-outcomes-body">
        <div className="analytics-audience-cards">
          <div>
            <MetricHeading icon={Users}>
              Tracked visits{visitsAreEstimated(period) ? ' (estimated)' : ''}
            </MetricHeading>
            <strong>
              {visitsAreEstimated(period) ? '≈ ' : ''}
              {n.format(report.audience.trackedVisits)}
            </strong>
            <p>
              {visitsAreEstimated(period)
                ? 'Estimated visits across searches and resource activity, tracked within each browser tab. These are not individual people; the estimate has about 0.81% relative standard error.'
                : 'Visits across searches and resource activity, tracked within each browser tab. These are not individual people.'}
            </p>
          </div>
        </div>
        {!embedded && (
          <>
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
                  <XAxis
                    dataKey="day"
                    tickFormatter={dateLabel}
                    minTickGap={35}
                  />
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
          </>
        )}
        <section aria-label="Daily audience values">
          <h3>Daily audience values</h3>
          <div className="analytics-comparison-scroll">
            <AnalyticsTable className="analytics-comparison-table">
              <caption>{outcomeLabels[period]} audience daily values</caption>
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">
                    Tracked visits
                    {visitsAreEstimated(period) ? ' (estimated)' : ''}
                  </th>
                  <th scope="col">Search result pages</th>
                  <th scope="col">Resource views</th>
                  <th scope="col">Source-site clicks</th>
                  <th scope="col">Download clicks</th>
                </tr>
              </thead>
              <tbody>
                {report.daily.map((row) => (
                  <tr key={row.day}>
                    <th scope="row">{row.day}</th>
                    <td data-sort-value={row.visits}>
                      {visitsAreEstimated(period) ? '≈ ' : ''}
                      {n.format(row.visits)}
                    </td>
                    <td>{n.format(row.searches)}</td>
                    <td>{n.format(row.views)}</td>
                    <td>{n.format(row.sources)}</td>
                    <td>{n.format(row.downloads)}</td>
                  </tr>
                ))}
              </tbody>
            </AnalyticsTable>
          </div>
        </section>
        <p className="analytics-comparison-note">
          {n.format(report.audience.activityRecords)} recorded searches and
          interactions contribute to this report.{' '}
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
          {visitsAreEstimated(period) ? outcomes.catalogDate : '2026-09-10'},
          UTC. Historical values are complete for these recorded event types,
          not a census of every visitor. The GA4/GTM connection and general SPA
          pageview coverage remain unverified.
        </p>
      </div>
    </Container>
  );
}

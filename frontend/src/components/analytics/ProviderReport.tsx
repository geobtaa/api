import { useAnalyticsData } from './AnalyticsData';
import { MetricHeading } from './MetricHeading';
import { AnalyticsTable } from './AnalyticsTable';
import { MemberContentList } from './MemberContentList';
import { RankingRow } from './RankingRow';
import { chartTheme } from './chartTheme';
import { useSearchParams } from 'react-router';
import { Activity, Users, Layers3, Eye, Download } from 'lucide-react';
import {
  CartesianGrid,
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ReportPanelHeader } from './ReportPanelHeader';
import type {
  ProviderSnapshot,
  Counts,
} from '../../data/analytics/providers2026';
const number = new Intl.NumberFormat('en-US');
const display = (value: number | null) =>
  value === null ? 'Unavailable' : number.format(value);
const columns: [keyof Counts, string][] = [
  ['catalogRecords', 'Catalog records'],
  ['activeResources', 'Active records'],
  ['resourceViews', 'Views'],
  ['impressions', 'Impressions'],
  ['downloadClicks', 'Download clicks'],
  ['sourceClicks', 'Source clicks'],
];

function providerSearchHref(provider: string) {
  const params = new URLSearchParams();
  params.append('include_filters[schema_provider_s][]', provider);
  return `/search?${params}`;
}

export function ProviderReport({
  month,
  snapshot: suppliedSnapshot,
}: {
  month: string;
  snapshot?: ProviderSnapshot;
}) {
  const { providerSnapshots } = useAnalyticsData().providers2026;
  const snapshot = suppliedSnapshot ?? providerSnapshots[month];
  const [params] = useSearchParams();
  const selected = params.get('provider') ?? 'all';
  if (!snapshot)
    return (
      <section
        className="analytics-panel analytics-report-sources"
        aria-label="Provider export status"
      >
        <h2>Provider grouping is awaiting its data export</h2>
        <p>
          The existing snapshots were calculated by contribution code. They
          cannot be converted into Provider totals. A separate aggregate export
          is required for {month}.
        </p>
        <p>
          This view will group the provider names saved in the catalog,
          including agencies, BTAA-named providers, and a Missing provider
          group. No university ownership is inferred from a contribution code.
        </p>
      </section>
    );
  const group = snapshot.groups.find((row) => row.id === selected);
  const counts = group ?? snapshot.totals;
  const rows = group ? [group] : snapshot.groups;
  const daily = (snapshot.groups[0]?.daily ?? []).map((point, index) => ({
    day: point.day,
    views: rows.reduce((n, row) => n + (row.daily[index]?.views ?? 0), 0),
    downloads: rows.reduce(
      (n, row) => n + (row.daily[index]?.downloads ?? 0),
      0
    ),
  }));
  return (
    <section className="analytics-section" aria-label="Provider report">
      {snapshot.impressionsAvailable === false && (
        <p className="analytics-comparison-note" role="note">
          July’s resource-level appearances in search results have expired.
          Search appearances and resources with activity are unavailable in this
          recalculation, not zero. Views, clicks, and daily series use complete
          July event records. The historical contribution-code report retains
          its previously exported figures.
        </p>
      )}
      <div className="analytics-member-kpi-grid">
        <article className="analytics-metric-card">
          <MetricHeading icon={Layers3}>Published resources</MetricHeading>
          <strong>{display(counts.catalogRecords)}</strong>
          <p>
            Published catalog inventory as of {snapshot.catalogSnapshotDate}
          </p>
        </article>
        <article className="analytics-metric-card">
          <MetricHeading icon={Activity}>Resources with activity</MetricHeading>
          <strong>{display(counts.activeResources)}</strong>
          <p>
            Resources appearing in search results or receiving views or clicks
          </p>
        </article>
        <article className="analytics-metric-card">
          <MetricHeading icon={Eye}>Resource views</MetricHeading>
          <strong>{display(counts.resourceViews)}</strong>
          <p>{display(counts.impressions)} appearances in search results</p>
        </article>
        <article className="analytics-metric-card">
          <MetricHeading icon={Download}>Download clicks</MetricHeading>
          <strong>{display(counts.downloadClicks)}</strong>
          <p>{display(counts.sourceClicks)} source-site clicks</p>
        </article>
      </div>
      <div className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader
          title="Daily views and download clicks"
          icon={Activity}
        />
        <div
          className="analytics-comparison-chart"
          role="img"
          aria-label={`Daily resource views and download clicks for ${group ? (group.provider ?? 'Missing provider') : 'all providers'} in ${month}. Exact values follow.`}
        >
          <ResponsiveContainer
            width="100%"
            height="100%"
            minWidth={0}
            initialDimension={{ width: 1000, height: 288 }}
          >
            <AreaChart data={daily}>
              <CartesianGrid {...chartTheme.grid} />
              <XAxis
                dataKey="day"
                tick={chartTheme.tick}
                axisLine={false}
                tickLine={false}
              />
              <YAxis tick={chartTheme.tick} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={chartTheme.tooltip}
                labelStyle={chartTheme.tooltipLabel}
                cursor={chartTheme.cursor}
              />
              <Area
                type="linear"
                dataKey="views"
                name="Views"
                stroke="#2563eb"
                fill="#2563eb"
                fillOpacity={0.12}
                dot={false}
                isAnimationActive={false}
              />
              <Area
                type="linear"
                dataKey="downloads"
                name="Downloads"
                stroke="#003c5b"
                fill="#003c5b"
                fillOpacity={0.04}
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <details>
          <summary>Daily values</summary>
          <div
            className="analytics-comparison-scroll"
            tabIndex={0}
            role="region"
            aria-label="Provider daily values"
          >
            <AnalyticsTable className="analytics-comparison-table">
              <caption className="sr-only">
                Provider daily views and downloads
              </caption>
              <thead>
                <tr>
                  <th scope="col">Day</th>
                  <th scope="col">Views</th>
                  <th scope="col">Download clicks</th>
                </tr>
              </thead>
              <tbody>
                {daily.map((row) => (
                  <tr key={row.day}>
                    <th scope="row">
                      {month}-{String(row.day).padStart(2, '0')}
                    </th>
                    <td>{number.format(row.views)}</td>
                    <td>{number.format(row.downloads)}</td>
                  </tr>
                ))}
              </tbody>
            </AnalyticsTable>
          </div>
        </details>
      </div>
      {group && (
        <div className="analytics-member-leading-content">
          <MemberContentList
            title={`Most viewed - ${group.provider ?? 'Missing provider'}`}
            items={group.topViews}
            metric="views"
            emptyMessage="No resource views were recorded."
          />
          <MemberContentList
            title={`Most download clicks - ${group.provider ?? 'Missing provider'}`}
            items={group.topDownloads}
            metric="downloads"
            emptyMessage="No download clicks were recorded."
          />
        </div>
      )}
      <section
        className="analytics-panel analytics-panel--ranking analytics-member-report"
        aria-label="Activity by provider"
      >
        <ReportPanelHeader title="Activity by provider" icon={Users}>
          <small>{rows.length} providers</small>
        </ReportPanelHeader>
        <div className="analytics-ranking-list">
          {[...rows]
            .sort((a, b) => b.resourceViews - a.resourceViews)
            .map((row, index) => (
              <RankingRow
                key={row.id}
                rank={index + 1}
                title={row.provider ?? 'Missing provider'}
                href={
                  row.provider ? providerSearchHref(row.provider) : undefined
                }
                value={row.resourceViews}
                label="views"
                maximum={Math.max(1, ...rows.map((row) => row.resourceViews))}
              >
                <dl className="analytics-member-row-details">
                  {columns
                    .filter(([key]) => key !== 'resourceViews')
                    .map(([key, label]) => (
                      <div key={key}>
                        <dt>{label}</dt>
                        <dd>{display(row[key])}</dd>
                      </div>
                    ))}
                </dl>
              </RankingRow>
            ))}
        </div>
      </section>
      <p className="analytics-comparison-note">
        Inventory and attribution use the catalog on{' '}
        {snapshot.catalogSnapshotDate}; activity covers {month}, UTC. Blank
        provider values appear as Missing provider. {snapshot.impressionSource}
      </p>
    </section>
  );
}

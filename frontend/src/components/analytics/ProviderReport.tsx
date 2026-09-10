import { useState } from 'react';
import { Link } from 'react-router';
import { Activity, Download, List, Users } from 'lucide-react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { ReportPanelHeader } from './ReportPanelHeader';
import {
  providerSnapshots,
  type ProviderSnapshot,
  type Counts,
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
  snapshot = providerSnapshots[month],
}: {
  month: string;
  snapshot?: ProviderSnapshot;
}) {
  const [selected, setSelected] = useState('all');
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
          This view will group the exact Provider facet values, including
          agencies, BTAA-named providers, and a Missing provider group. No
          university ownership is inferred from a contribution code.
        </p>
      </section>
    );
  const group = snapshot.groups.find((row) => row.id === selected);
  const counts = group ?? snapshot.totals;
  const rows = group ? [group] : snapshot.groups;
  const daily = Array.from({ length: 31 }, (_, index) => ({
    day: index + 1,
    views: rows.reduce((n, row) => n + row.daily[index].views, 0),
    downloads: rows.reduce((n, row) => n + row.daily[index].downloads, 0),
  }));
  const download = `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify({ ...snapshot, selection: group ? (group.provider ?? 'Missing provider') : 'All providers', selectedTotals: counts, groups: rows }, null, 2))}`;
  return (
    <section className="analytics-section" aria-label="Provider report">
      <div className="analytics-grouping-controls">
        <label htmlFor="analytics-provider">Provider</label>
        <select
          id="analytics-provider"
          value={group ? selected : 'all'}
          onChange={(event) => setSelected(event.target.value)}
        >
          <option value="all">All providers</option>
          {snapshot.groups.map((row) => (
            <option key={row.id} value={row.id}>
              {row.provider ?? 'Missing provider'}
            </option>
          ))}
        </select>
        {group?.provider && (
          <Link to={providerSearchHref(group.provider)}>
            Browse this provider
          </Link>
        )}
      </div>
      <p className="analytics-comparison-note">
        Exact values of the Provider facet (<code>schema_provider_s</code>),
        independent of contribution codes. Inventory and attribution use the
        catalog on {snapshot.catalogSnapshotDate}; activity covers {month}, UTC.
        Other agencies retain their own names; blank values appear as Missing
        provider.
      </p>
      {snapshot.impressionsAvailable === false && (
        <p className="analytics-comparison-note" role="note">
          July’s resource-level search impressions have expired. Impressions and
          active-record reach are unavailable in this recalculation, not zero.
          Views, clicks, and daily series use complete July event records. The
          historical contribution-code report retains its previously exported
          figures.
        </p>
      )}
      <div className="analytics-client-highlights">
        {columns.map(([key, label]) => (
          <article
            className="analytics-panel analytics-comparison-panel"
            key={key}
          >
            <h2>{label}</h2>
            <strong>{display(counts[key])}</strong>
          </article>
        ))}
      </div>
      <div className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader title="Daily views and downloads" icon={Activity} />
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
            <LineChart data={daily}>
              <CartesianGrid strokeDasharray="2 6" />
              <XAxis dataKey="day" />
              <YAxis />
              <Tooltip />
              <Line
                type="linear"
                dataKey="views"
                name="Views"
                stroke="#2563eb"
                dot={false}
                isAnimationActive={false}
              />
              <Line
                type="linear"
                dataKey="downloads"
                name="Downloads"
                stroke="#003c5b"
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
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
            <table className="analytics-comparison-table">
              <caption className="sr-only">
                Provider daily views and downloads
              </caption>
              <thead>
                <tr>
                  <th scope="col">Day</th>
                  <th scope="col">Views</th>
                  <th scope="col">Downloads</th>
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
            </table>
          </div>
        </details>
      </div>
      {group && (
        <div className="analytics-panel analytics-comparison-panel">
          <ReportPanelHeader title="Leading content" icon={List} />
          {(['topViews', 'topDownloads'] as const).map((key) => (
            <div key={key}>
              <h3>{key === 'topViews' ? 'Most viewed' : 'Most downloaded'}</h3>
              {group[key].length ? (
                <ol>
                  {group[key].map((row) => (
                    <li key={row.id}>
                      <Link to={`/resources/${encodeURIComponent(row.id)}`}>
                        {row.title}
                      </Link>{' '}
                      —{' '}
                      {number.format(
                        key === 'topViews' ? row.views : row.downloads
                      )}
                    </li>
                  ))}
                </ol>
              ) : (
                <p>No matching events recorded.</p>
              )}
            </div>
          ))}
        </div>
      )}
      <div className="analytics-panel analytics-comparison-panel">
        <ReportPanelHeader title="Provider totals" icon={Users}>
          <a href={download} download={`analytics-providers-${month}.json`}>
            <Download aria-hidden="true" />
            Download provider data
          </a>
        </ReportPanelHeader>
        <div
          className="analytics-comparison-scroll"
          tabIndex={0}
          role="region"
          aria-label="Provider totals table"
        >
          <table className="analytics-comparison-table">
            <caption className="sr-only">{month} Provider totals</caption>
            <thead>
              <tr>
                <th scope="col">Provider</th>
                {columns.map(([key, label]) => (
                  <th scope="col" key={key}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <th scope="row">{row.provider ?? 'Missing provider'}</th>
                  {columns.map(([key]) => (
                    <td key={key}>{display(row[key])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

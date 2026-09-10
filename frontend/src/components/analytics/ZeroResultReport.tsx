import { FailedSearchContext } from './FailedSearchContext';
import {
  outcomes,
  searchContexts,
  type OutcomePeriod,
} from '../../data/analytics/outcomes';
import { useState } from 'react';
import { Link } from 'react-router';
import { Search } from 'lucide-react';
import { zeroQueryCategory } from '../../data/analytics/zeroQueryCategory';
import { AnalyticsTable } from './AnalyticsTable';
import { ReportPanelHeader } from './ReportPanelHeader';

const number = new Intl.NumberFormat('en-US');
const percent = (count: number, total: number) =>
  total ? `${((count / total) * 100).toFixed(1)}%` : '0.0%';
const colors = [
  '#003c5b',
  '#2563eb',
  '#047857',
  '#9333ea',
  '#b45309',
  '#be185d',
  '#0e7490',
  '#4f46e5',
  '#4d7c0f',
  '#9f1239',
  '#475569',
  '#7c2d12',
];
function Pie({
  title,
  slices,
  total,
}: {
  title: string;
  slices: { label: string; count: number }[];
  total: number;
}) {
  let cursor = 0;
  const stops = slices.map((slice, index) => {
    const start = cursor;
    cursor += total ? (slice.count / total) * 100 : 0;
    return `${colors[index % colors.length]} ${start}% ${cursor}%`;
  });
  return (
    <div className="analytics-zero-pie">
      <h3>{title}</h3>
      <div className="analytics-donut-layout">
        <div
          className="analytics-donut"
          role="img"
          aria-label={`${title}: ${slices.map((slice) => `${slice.label} ${number.format(slice.count)} (${percent(slice.count, total)})`).join('; ')}`}
          style={{
            background: total
              ? `conic-gradient(${stops.join(',')})`
              : '#e5e7eb',
          }}
        >
          <div>
            <strong>{number.format(total)}</strong>
            <span>searches</span>
          </div>
        </div>
        <ul>
          {slices.map((slice, index) => (
            <li key={slice.label}>
              <i
                style={{ backgroundColor: colors[index % colors.length] }}
                aria-hidden="true"
              />
              <span>{slice.label}</span>
              <strong>
                {number.format(slice.count)} · {percent(slice.count, total)}
              </strong>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
export function ZeroResultReport({
  period,
  periodKey,
  searches,
  zeroResults,
  withQuery,
  queries,
}: {
  period: string;
  periodKey?: OutcomePeriod;
  searches: number;
  zeroResults: number;
  withQuery: number;
  queries: { term: string; count: number }[];
}) {
  const [category, setCategory] = useState('all');
  const rows = queries.map((q, index) => ({
    ...q,
    rank: index + 1,
    category: zeroQueryCategory(q.term),
  }));
  const counts = new Map<string, number>();
  rows.forEach((row) =>
    counts.set(row.category, (counts.get(row.category) ?? 0) + row.count)
  );
  const slices = [...counts]
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count);
  const ranked = rows.reduce((n, row) => n + row.count, 0);
  const selected = slices.some((slice) => slice.label === category)
    ? category
    : 'all';
  return (
    <section className="analytics-panel analytics-zero-results">
      <ReportPanelHeader title="Zero-result searches" icon={Search} />
      <div className="analytics-zero-results-body">
        <p className="analytics-zero-rate">
          <strong>{percent(zeroResults, searches)}</strong> of searches returned
          zero results — {number.format(zeroResults)} of{' '}
          {number.format(searches)} searches in {period}.
        </p>
        {periodKey && (
          <p className="analytics-comparison-note">
            Historical counts use the recorded zero-result flag.{' '}
            {outcomes.periods[periodKey].zeroResultsWithPositiveTotal} flagged
            searches had a positive total but an empty displayed page. Expand
            recorded combinations to inspect exclusions, pagination, and other
            saved controls.
          </p>
        )}
        <div className="analytics-zero-charts">
          <Pie
            title="Search outcomes"
            total={searches}
            slices={[
              { label: 'With results', count: searches - zeroResults },
              { label: 'Zero results', count: zeroResults },
            ]}
          />
          <Pie
            title="Zero-result query categories"
            total={ranked}
            slices={slices}
          />
        </div>
        <p className="analytics-comparison-note">
          The category chart covers the {number.format(ranked)} zero-result
          searches represented by the {rows.length} ranked queries below, not
          all {number.format(zeroResults)} zero-result searches.{' '}
          {number.format(withQuery)} included query text;{' '}
          {number.format(zeroResults - withQuery)} were filter-only searches
          with no query. Categories are inferred from wording, not verified
          failure causes; reviewed August classifications are preserved, and
          unclear queries remain unclassified.
        </p>
        <label className="analytics-query-category-filter">
          Zero-result category
          <select
            value={selected}
            onChange={(event) => setCategory(event.target.value)}
          >
            <option value="all">All categories</option>
            {slices.map((slice) => (
              <option key={slice.label}>{slice.label}</option>
            ))}
          </select>
        </label>
        <div
          role="region"
          aria-label="Zero-result queries"
          className="analytics-comparison-scroll"
        >
          <AnalyticsTable className="analytics-comparison-table">
            <caption className="sr-only">{period} zero-result queries</caption>
            <thead>
              <tr>
                <th scope="col">Rank</th>
                <th scope="col">Query</th>
                <th scope="col">Category</th>
                {periodKey && <th scope="col">Recorded search context</th>}
                <th scope="col">Zero-result searches</th>
                <th scope="col">Share of all zero-result searches</th>
              </tr>
            </thead>
            <tbody>
              {rows
                .filter(
                  (row) => selected === 'all' || row.category === selected
                )
                .map((row) => (
                  <tr key={row.term}>
                    <td>{row.rank}</td>
                    <th scope="row">
                      <Link to={`/search?q=${encodeURIComponent(row.term)}`}>
                        {row.term}
                      </Link>
                    </th>
                    <td>{row.category}</td>
                    {periodKey && (
                      <td
                        className="analytics-context-cell"
                        data-sort-value={
                          searchContexts(periodKey, row.term).length
                        }
                        data-filter-value={JSON.stringify(
                          searchContexts(periodKey, row.term)
                        )}
                      >
                        <FailedSearchContext
                          period={periodKey}
                          term={row.term}
                        />
                      </td>
                    )}
                    <td>{row.count}</td>
                    <td>{percent(row.count, zeroResults)}</td>
                  </tr>
                ))}
            </tbody>
          </AnalyticsTable>
        </div>
        {periodKey && (
          <details className="analytics-blank-context">
            <summary>Searches without query text: recorded parameters</summary>
            <FailedSearchContext period={periodKey} term="" />
          </details>
        )}
        <p className="analytics-comparison-note">
          These {rows.length} queries account for {number.format(ranked)}{' '}
          zero-result searches. Additional filters may have caused zero results;
          query links repeat the text only. Row percentages use all zero-result
          searches as the denominator, not the failure rate of that particular
          query. Charts remain based on the full period when the table is
          filtered.
        </p>
      </div>
    </section>
  );
}

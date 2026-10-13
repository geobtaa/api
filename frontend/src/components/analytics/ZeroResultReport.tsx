import { useAnalyticsData } from './AnalyticsData';
import { FailedSearchContext } from './FailedSearchContext';
import type { OutcomePeriod } from '../../data/analytics/outcomes';
import { useState } from 'react';
import { Search } from 'lucide-react';

import { RankingRow } from './RankingRow';
import { ReportPanelHeader } from './ReportPanelHeader';

const number = new Intl.NumberFormat('en-US');
const percent = (count: number, total: number) =>
  total ? `${((count / total) * 100).toFixed(1)}%` : '0.0%';
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
  const analytics = useAnalyticsData();
  const outcomes = analytics['outcomes'].outcomes;
  const searchContexts = analytics['outcomes'].searchContexts;
  const zeroQueryCategory = analytics['zeroQueryCategory'].zeroQueryCategory;

  const [category, setCategory] = useState('all');
  const [filter, setFilter] = useState('');
  const [sort, setSort] = useState('count');
  const rows = queries.map((q, index) => ({
    ...q,
    rank: index + 1,
    translation:
      analytics.queryTranslations[q.term.trim().replace(/\s+/g, ' ')],
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
  const terms = filter.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const visible = rows
    .filter(
      (row) =>
        (selected === 'all' || row.category === selected) &&
        terms.every((term) =>
          `${row.term} ${row.translation?.english ?? ''} ${row.category} ${periodKey ? JSON.stringify(searchContexts(periodKey, row.term)) : ''}`
            .toLowerCase()
            .includes(term)
        )
    )
    .sort((a, b) =>
      sort === 'query'
        ? a.term.localeCompare(b.term)
        : b.count - a.count || a.rank - b.rank
    );
  const maximum = Math.max(1, ...rows.map((row) => row.count));
  return (
    <section
      id="zero-results"
      className="analytics-panel analytics-zero-results"
    >
      <ReportPanelHeader title="Searches without results" icon={Search} />
      <div className="analytics-zero-results-body">
        <div className="analytics-zero-summary">
          <article className="analytics-metric-card">
            <span>Searches without results</span>
            <strong>{number.format(zeroResults)}</strong>
            <p>
              <b>{percent(zeroResults, searches)}</b> of{' '}
              {number.format(searches)} searches in {period}
            </p>
          </article>
          <article className="analytics-metric-card">
            <span>With query text</span>
            <strong>{number.format(withQuery)}</strong>
            <p>Searches with words or phrases to investigate.</p>
          </article>
          <article className="analytics-metric-card">
            <span>Filters only</span>
            <strong>{number.format(zeroResults - withQuery)}</strong>
            <p>Searches without query text; inspect the recorded filters.</p>
          </article>
        </div>
        <div className="analytics-zero-analysis">
          <section className="analytics-zero-outcomes">
            <h3>Search outcomes</h3>
            <p>Across all searches in the selected period.</p>
            <div
              className="analytics-zero-outcome-bar"
              role="img"
              aria-label={`Search outcomes: With results ${number.format(searches - zeroResults)} (${percent(searches - zeroResults, searches)}); Zero results ${number.format(zeroResults)} (${percent(zeroResults, searches)})`}
            >
              <span
                style={{
                  width: `${searches ? ((searches - zeroResults) / searches) * 100 : 0}%`,
                }}
              />
              <span
                style={{
                  width: `${searches ? (zeroResults / searches) * 100 : 0}%`,
                }}
              />
            </div>
            <div className="analytics-zero-outcome-labels">
              <div>
                <span>With results</span>
                <strong>{number.format(searches - zeroResults)}</strong>
              </div>
              <div>
                <span>Zero results</span>
                <strong>{number.format(zeroResults)}</strong>
              </div>
            </div>
          </section>
          <section className="analytics-zero-categories">
            <h3>Topics in searches without results</h3>
            <p>
              {number.format(ranked)} searches across {rows.length} ranked
              queries, not all {number.format(zeroResults)} zero-result
              searches.
            </p>
            <div
              role="img"
              aria-label={`Topics in searches without results: ${slices.map((slice) => `${slice.label} ${slice.count} (${percent(slice.count, ranked)})`).join('; ')}`}
            >
              {slices.map((slice) => (
                <div className="analytics-zero-category-row" key={slice.label}>
                  <div>
                    <span>{slice.label}</span>
                    <strong>{number.format(slice.count)}</strong>
                  </div>
                  <div className="analytics-format-track" aria-hidden="true">
                    <i
                      style={{
                        width: `${(slice.count / Math.max(1, ...slices.map((s) => s.count))) * 100}%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
            <p className="analytics-zero-caveat">
              Categories describe query wording, not proven failure causes.
            </p>
          </section>
        </div>
        <div className="analytics-zero-ranking-heading">
          <h3>Search terms to review</h3>
          <p>
            Ranked by zero-result searches. Open the recorded details to inspect
            filters and other search settings.
          </p>
        </div>
        <div className="analytics-table-tools analytics-zero-toolbar">
          <label>
            Find a query
            <input
              type="search"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Search queries, categories, or details…"
            />
          </label>
          <label>
            Zero-result category
            <select
              value={selected}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="all">All categories</option>
              {slices.map((s) => (
                <option key={s.label}>{s.label}</option>
              ))}
            </select>
          </label>
          <label>
            Sort by
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="count">Most zero-result searches</option>
              <option value="query">Query A–Z</option>
            </select>
          </label>
          <span role="status">
            {visible.length} of {rows.length} queries
          </span>
          <button
            type="button"
            disabled={!filter && selected === 'all' && sort === 'count'}
            onClick={() => {
              setFilter('');
              setCategory('all');
              setSort('count');
            }}
          >
            Reset
          </button>
        </div>
        <div
          role="region"
          aria-label="Search terms without results"
          className="analytics-ranking-list analytics-zero-ranking"
        >
          {visible.map((row) => (
            <RankingRow
              key={row.term}
              rank={row.rank}
              title={row.term}
              href={`/search?q=${encodeURIComponent(row.term)}`}
              subtitle={
                row.translation && (
                  <p className="analytics-query-translation" lang="en">
                    <strong>English:</strong> {row.translation.english}
                    <span>
                      {' '}
                      · {row.translation.language}
                      {row.translation.note ? ` — ${row.translation.note}` : ''}
                    </span>
                  </p>
                )
              }
              description={row.category}
              value={row.count}
              label="zero-result searches"
              maximum={maximum}
            >
              <p className="analytics-zero-query-share">
                {percent(row.count, zeroResults)} of all zero-result searches
              </p>
              {periodKey && (
                <FailedSearchContext period={periodKey} term={row.term} />
              )}
            </RankingRow>
          ))}
          {!visible.length && (
            <p className="analytics-zero-empty">
              No queries match these filters. Try another term or reset the
              filters.
            </p>
          )}
        </div>
        {periodKey && (
          <details className="analytics-zero-details">
            <summary>Filter-only searches: recorded details</summary>
            <FailedSearchContext period={periodKey} term="" />
          </details>
        )}
        <details className="analytics-zero-details">
          <summary>About these counts</summary>
          <p>
            These {rows.length} queries account for {number.format(ranked)}{' '}
            zero-result searches. Additional filters may have caused zero
            results; query links repeat the text only. Each percentage is a
            share of all searches without results, not the percentage of times
            that particular term failed. Charts remain based on the full period
            when the rankings are filtered.
          </p>
          <p>
            English readings are editorial translations or transliterations of
            saved queries; ambiguous names and incomplete phrases are labeled.
            Original query text and search links are preserved. Categories are
            inferred from wording; reviewed August classifications are
            preserved, and unclear queries remain unclassified.
          </p>
          {periodKey && (
            <p>
              Historical counts use the recorded zero-result flag.{' '}
              {outcomes.periods[periodKey].zeroResultsWithPositiveTotal} flagged
              searches had a positive total but an empty displayed page. Expand
              the saved search details to review excluded filters, the selected
              results page, and other settings.
            </p>
          )}
        </details>
      </div>
    </section>
  );
}

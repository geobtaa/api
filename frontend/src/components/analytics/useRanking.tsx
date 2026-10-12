import { useId, useState } from 'react';

export function useRanking<T extends { title: string; provider?: string }>(
  rows: T[],
  count: (row: T) => number,
  label: string,
  metricLabel = label === 'Top resources' ? 'views' : 'clicks'
) {
  const id = useId();
  const [query, setQuery] = useState('');
  const [order, setOrder] = useState('count');
  const terms = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const visible = rows
    .map((row, index) => ({ row, rank: index + 1 }))
    .filter(({ row }) =>
      terms.every((term) =>
        `${row.title} ${row.provider ?? ''}`.toLowerCase().includes(term)
      )
    )
    .sort((a, b) =>
      order === 'title'
        ? a.row.title.localeCompare(b.row.title)
        : order === 'provider'
          ? (a.row.provider ?? '').localeCompare(b.row.provider ?? '')
          : count(b.row) - count(a.row)
    );
  return {
    visible,
    controls: (
      <div className="analytics-table-tools analytics-table-tools--inset">
        <label htmlFor={id}>
          Filter resources
          <input
            id={id}
            type="search"
            aria-label={`Filter ${label}`}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={
              rows.some((row) => row.provider)
                ? 'Search titles or providers…'
                : 'Search titles…'
            }
          />
        </label>
        <label>
          Sort by
          <select
            aria-label={`Sort ${label}`}
            value={order}
            onChange={(event) => setOrder(event.target.value)}
          >
            <option value="count">Most {metricLabel}</option>
            <option value="title">Title</option>
            {rows.some((row) => row.provider) && (
              <option value="provider">Provider</option>
            )}
          </select>
        </label>
        <span role="status">
          {visible.length} of {rows.length} resources
        </span>
      </div>
    ),
  };
}

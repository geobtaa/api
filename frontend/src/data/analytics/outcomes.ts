import snapshot from './outcomes2026.json';
export type OutcomePeriod = '2026-07' | '2026-08' | 'all';
export type SearchContext = {
  constraints: Record<string, unknown>;
  page: number | null;
  view: string | null;
  sort: string | null;
  searchField: string | null;
  resultsCount: number | null;
  totalPages: number | null;
  count: number;
};
export const outcomes = snapshot;
export const outcomeLabels = {
  '2026-07': 'July 2026',
  '2026-08': 'August 2026',
  all: 'July–August 2026',
};
export function searchContexts(
  period: OutcomePeriod,
  term: string
): SearchContext[] {
  return (
    (
      snapshot.periods[period].zeroResultContexts as Record<
        string,
        SearchContext[]
      >
    )[term] ?? []
  );
}

const display = (value: unknown): string =>
  typeof value === 'string' ? value : JSON.stringify(value);
export function replaySearch(term: string, context: SearchContext) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(context.constraints)) {
    if (Array.isArray(value))
      value.forEach((item) => params.append(key, display(item)));
    else if (value !== null) params.set(key, display(value));
  }
  params.set('q', term);
  for (const [key, value] of Object.entries({
    page: context.page,
    view: context.view,
    sort: context.sort,
    search_field: context.searchField,
  })) {
    if (value !== null && !params.has(key)) params.set(key, String(value));
  }
  return `/search?${params}`;
}

import {
  publishedMonths,
  monthLabel,
  comparisonLabel,
} from '../../config/analyticsPeriods';
import historical from './outcomes2026.json';
import latest from './outcomesCurrent.json';
const snapshot = {
  ...historical,
  ...latest,
  periods: { ...historical.periods, ...latest.periods },
};
export type OutcomePeriod = string;
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
const periods: Record<
  string,
  (typeof snapshot.periods)[keyof typeof snapshot.periods]
> = snapshot.periods;
export const outcomes = { ...snapshot, periods };
export const outcomeLabels: Record<string, string> = {
  ...Object.fromEntries(publishedMonths.map((m) => [m, monthLabel(m)])),
  all: comparisonLabel,
};
export function searchContexts(
  period: OutcomePeriod,
  term: string
): SearchContext[] {
  return (
    (periods[period].zeroResultContexts as Record<string, SearchContext[]>)[
      term
    ] ?? []
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

export function withheldSearchContexts(
  period: OutcomePeriod,
  term: string
): number {
  const report = outcomes.periods[period];
  return 'withheldSearchContexts' in report
    ? ((report.withheldSearchContexts as Record<string, number>)[term] ?? 0)
    : 0;
}

export function visitsAreEstimated(period: OutcomePeriod): boolean {
  const audience = periods[period].audience;
  return 'estimated' in audience && audience.estimated === true;
}

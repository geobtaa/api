import type { AnalyticsData } from './AnalyticsData';
import type {
  ClientSnapshot,
  ClientUsage,
} from '../../data/analytics/clients2026';
import type {
  OutcomePeriod,
  SearchContext,
} from '../../data/analytics/outcomes';
/** Combine disjoint months; unavailable evidence stays unavailable. */
export function combineClientSnapshots(
  snapshots: ClientSnapshot[]
): ClientSnapshot {
  const clients = new Map<string, ClientUsage>();
  const surfaces = new Map<string, number>();
  for (const snapshot of snapshots) {
    for (const row of snapshot.clients) {
      const key = JSON.stringify([row.name, row.channel]);
      const old = clients.get(key) ?? {
        ...row,
        requests: 0,
        searches: 0,
        events: 0,
      };
      clients.set(key, {
        ...row,
        requests: old.requests + row.requests,
        searches: old.searches + row.searches,
        events: old.events + row.events,
      });
    }
    for (const row of snapshot.surfaces)
      surfaces.set(row.label, (surfaces.get(row.label) ?? 0) + row.requests);
  }
  return {
    clients: [...clients.values()].sort((a, b) => b.requests - a.requests),
    surfaces: [...surfaces]
      .map(([label, requests]) => ({ label, requests }))
      .sort((a, b) => b.requests - a.requests),
    // Without key identities, nonzero monthly distinct counts cannot be combined.
    recordedKeys: snapshots.every((row) => row.recordedKeys === 0) ? 0 : null,
    keyAttributedRequests: snapshots.reduce(
      (n, row) => n + row.keyAttributedRequests,
      0
    ),
    unattributedKeyRequests: snapshots.reduce(
      (n, row) => n + row.unattributedKeyRequests,
      0
    ),
    qgisUserAgentRequests: snapshots.some(
      (row) => row.qgisUserAgentRequests === null
    )
      ? null
      : snapshots.reduce((n, row) => n + row.qgisUserAgentRequests!, 0),
  };
}

export function restoreAnalyticsHelpers(
  snapshot: AnalyticsData
): AnalyticsData {
  const outcomes = snapshot.outcomes.outcomes;
  const periods = outcomes.periods;
  const normalize = (term: string) =>
    term.trim().replace(/\s+/g, ' ').toLocaleLowerCase('en-US');
  const categories = new Map(
    Object.entries(snapshot.queryCategories.groups).flatMap(
      ([category, terms]) =>
        terms.map((term) => [normalize(term), category] as const)
    )
  );
  const hasReviewedQueryCategory = (term: string) =>
    categories.has(normalize(term));
  const queryCategory = (term: string) =>
    categories.get(normalize(term)) ?? 'Mixed or unclear';
  const reviewed = snapshot['zeroQueryCategories.json'].default;
  function searchContexts(
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
  function replaySearch(term: string, context: SearchContext) {
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

  function withheldSearchContexts(period: OutcomePeriod, term: string): number {
    const report = outcomes.periods[period];
    return 'withheldSearchContexts' in report
      ? ((report.withheldSearchContexts as Record<string, number>)[term] ?? 0)
      : 0;
  }

  function visitsAreEstimated(period: OutcomePeriod): boolean {
    const audience = periods[period].audience;
    return 'estimated' in audience && audience.estimated === true;
  }

  function zeroQueryCategory(term: string): string {
    const category = (reviewed as Record<string, string>)[term];
    if (category) return category;
    if (/^[+-]?\d{1,3}\.\d+\s*,\s*[+-]?\d{1,3}\.\d+$/.test(term.trim()))
      return 'Coordinates and Plus Codes';
    if (/\b(township|range|section)\b|\bT\d+N\b/i.test(term))
      return 'Township/range/section and land descriptions';
    if (
      /\b(street|avenue|road|lane|drive|blvd|addr|address)\b|^\d+\s+.*\b(st|ave|rd|ln|dr|way|ct)\b/i.test(
        term
      )
    )
      return 'Address and street search';
    if (/^\d{4}$/.test(term.trim())) return 'Date-only search';
    const inferred = queryCategory(term);
    if (inferred === 'Places & regions')
      return 'Named places and postal geography';
    if (inferred === 'Maps & imagery')
      return 'Subject or map series plus place/date';
    if (
      [
        'Environment & land use',
        'Society & history',
        'Transport & infrastructure',
      ].includes(inferred)
    )
      return 'Subject-only search';
    if (inferred === 'People & institutions' || inferred === 'Catalogs & tools')
      return 'Known map, title, citation, or creator';
    if (inferred === 'Addresses & coordinates')
      return 'Address and street search';
    return 'Unclassified or ambiguous';
  }

  type Baseline = Record<
    'collections' | 'downloads' | 'outlinks',
    Record<string, number>
  >;
  const baselines = snapshot['popularMomentumCurrent.json'].default as Record<
    string,
    Baseline | null
  >;

  function previousRankingValue(
    period: string | undefined,
    ranking: keyof Baseline,
    id: string | null
  ) {
    if (!period || period === 'all') return undefined;
    const baseline = baselines[period];
    if (!baseline || id == null) return null;
    return baseline[ranking][id] ?? 0;
  }

  return {
    ...snapshot,
    clients2026: { ...snapshot.clients2026, combineClientSnapshots },
    outcomes: {
      ...snapshot.outcomes,
      searchContexts,
      replaySearch,
      withheldSearchContexts,
      visitsAreEstimated,
    },
    queryCategories: {
      ...snapshot.queryCategories,
      hasReviewedQueryCategory,
      queryCategory,
    },
    zeroQueryCategory: { zeroQueryCategory },
    popularMomentum: { previousRankingValue },
  };
}

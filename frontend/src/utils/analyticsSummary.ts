import type { AnalyticsData } from '../components/analytics/AnalyticsData';
import { latestMonth, monthLabel } from '../config/analyticsPeriods';

const DAY = 86_400_000;
const iso = (date: Date) => date.toISOString().slice(0, 10);

type AccessMonth = {
  period: string;
  label: string;
  sources: number | null;
  downloads: number | null;
};

/** Preserve the whole window and unavailable counts while limiting chart density. */
export function groupAccessMonths(months: AccessMonth[]) {
  const ordered = [...months].sort((a, b) => a.period.localeCompare(b.period));
  const quarters = new Set(
    ordered.map((row) => {
      const [year, month] = row.period.split('-').map(Number);
      return `${year}-${Math.floor((month - 1) / 3)}`;
    })
  );
  // A window crossing calendar-quarter boundaries can touch 13 quarters.
  const unit =
    ordered.length <= 12
      ? 'month'
      : ordered.length <= 36 && quarters.size <= 12
        ? 'quarter'
        : 'year';
  const firstYear = Number(ordered[0]?.period.slice(0, 4) ?? 0);
  const lastYear = Number(ordered.at(-1)?.period.slice(0, 4) ?? firstYear);
  const yearsPerBar = Math.max(1, Math.ceil((lastYear - firstYear + 1) / 12));
  const groups = new Map<
    string,
    { label: string; expectedMonths: number; months: AccessMonth[] }
  >();
  for (const row of ordered) {
    const [year, month] = row.period.split('-').map(Number);
    const startYear =
      firstYear + Math.floor((year - firstYear) / yearsPerBar) * yearsPerBar;
    const endYear = startYear + yearsPerBar - 1;
    const quarter = Math.floor((month - 1) / 3) + 1;
    const key =
      unit === 'month'
        ? row.period
        : unit === 'quarter'
          ? `${year}-Q${quarter}`
          : String(startYear);
    const label =
      unit === 'month'
        ? row.label
        : unit === 'quarter'
          ? `Q${quarter} ${year}`
          : yearsPerBar === 1
            ? String(year)
            : `${startYear}–${endYear}`;
    const group = groups.get(key) ?? {
      label,
      expectedMonths:
        unit === 'month' ? 1 : unit === 'quarter' ? 3 : yearsPerBar * 12,
      months: [],
    };
    group.months.push(row);
    groups.set(key, group);
  }
  const sum = (rows: AccessMonth[], key: 'sources' | 'downloads') =>
    rows.some((row) => row[key] === null)
      ? null
      : rows.reduce((total, row) => total + row[key]!, 0);
  return {
    unit,
    description:
      unit === 'month'
        ? 'Monthly counts'
        : unit === 'quarter'
          ? 'Quarterly counts'
          : yearsPerBar === 1
            ? 'Yearly counts'
            : `Counts by ${yearsPerBar}-year period`,
    rows: [...groups].map(([period, group]) => ({
      period,
      label: `${group.label}${group.months.length < group.expectedMonths ? ' (partial)' : ''}`,
      sources: sum(group.months, 'sources'),
      downloads: sum(group.months, 'downloads'),
    })),
  };
}

type ResourceAccessCounts = {
  id: string;
  title: string;
  views: number;
  sources: number;
  downloads: number;
};

export type ResourceAccessPattern = ResourceAccessCounts & {
  clicks: number;
  clicksPer100Views: number;
};

/** Event-count ratios, not visit conversion rates. Keep this preview small. */
export function resourceAccessPatterns(resources: ResourceAccessCounts[]) {
  const eligible = resources
    .filter((row) => row.views >= 20)
    .map((row) => ({
      ...row,
      clicks: row.sources + row.downloads,
      clicksPer100Views: ((row.sources + row.downloads) / row.views) * 100,
    }));
  const tieBreak = (a: ResourceAccessCounts, b: ResourceAccessCounts) =>
    b.views - a.views || a.id.localeCompare(b.id);
  return {
    fewerClicks: [...eligible]
      .sort(
        (a, b) => a.clicksPer100Views - b.clicksPer100Views || tieBreak(a, b)
      )
      .slice(0, 5),
    moreClicks: eligible
      .filter((row) => row.clicks > 0)
      .sort(
        (a, b) => b.clicksPer100Views - a.clicksPer100Views || tieBreak(a, b)
      )
      .slice(0, 5),
  };
}

function reportingWindow(start: string, endExclusive: string) {
  const first = new Date(`${start}T00:00:00Z`);
  const end = new Date(`${endExclusive}T00:00:00Z`);
  const monthCount =
    (end.getUTCFullYear() - first.getUTCFullYear()) * 12 +
    end.getUTCMonth() -
    first.getUTCMonth();
  return {
    start,
    endExclusive,
    end: iso(new Date(end.getTime() - DAY)),
    months: Array.from({ length: monthCount }, (_, index) =>
      iso(
        new Date(
          Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + index, 1)
        )
      ).slice(0, 7)
    ),
  };
}

/** Anchor to the latest published month, never imply that saved data is live. */
export function summaryWindow(month = latestMonth, monthCount = 3) {
  const [year, number] = month.split('-').map(Number);
  return reportingWindow(
    iso(new Date(Date.UTC(year, number - monthCount, 1))),
    iso(new Date(Date.UTC(year, number, 1)))
  );
}

export function summaryDate(day: string) {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

export function buildAnalyticsSummary(
  analytics: Pick<
    AnalyticsData,
    | 'outcomes'
    | 'allTimeCurrent.json'
    | 'monthlySnapshots.json'
    | 'topSearches2026.json'
    | 'searches2026'
    | 'providers2026'
  >,
  month = latestMonth,
  selection: '3months' | 'month' | 'all' = '3months'
) {
  const allTime = analytics['allTimeCurrent.json'].default;
  const window =
    selection === 'all'
      ? reportingWindow(allTime.start, allTime.endExclusive)
      : summaryWindow(month, selection === 'month' ? 1 : 3);
  const periods = analytics.outcomes.outcomes.periods;
  // Monthly periods are disjoint. Do not combine them with the overlapping "all" period.
  const publishedDays = Object.entries(periods)
    .filter(([period]) => /^\d{4}-\d{2}$/.test(period))
    .flatMap(([, period]) => period.daily);
  const daily = publishedDays
    .filter((row) => row.day >= window.start && row.day < window.endExclusive)
    .sort((a, b) => a.day.localeCompare(b.day));
  // Ranking exports are truncated. Only use a precomputed ranking for the exact
  // window; summing monthly top-N lists can give incorrect totals and ordering.
  const rankedOutcomes = Object.values(periods).find(
    (period) =>
      period.start === window.start &&
      period.endExclusive === window.endExclusive
  );
  const rankedSearches =
    allTime.start === window.start &&
    allTime.endExclusive === window.endExclusive
      ? allTime
      : null;
  const snapshot = Object.entries(
    analytics['monthlySnapshots.json'].default
  ).find(([period]) => period === month)?.[1];
  const historicalSearches = Object.entries(
    analytics['topSearches2026.json'].default.months
  ).find(([period]) => period === month)?.[1];
  const historicalZero = Object.entries(
    analytics.searches2026.searchSnapshots
  ).find(([period]) => period === month)?.[1];
  const catalog =
    snapshot?.provider ?? analytics.providers2026.providerSnapshots[month];
  // Catalog capture dates differ from activity months. July and August can
  // share one capture, which is not evidence of zero growth between months.
  const catalogSnapshots = [
    ...Object.values(analytics.providers2026.providerSnapshots),
    ...Object.values(analytics['monthlySnapshots.json'].default).map(
      (row) => row.provider
    ),
  ].flatMap((row) => (row ? [row] : []));
  const previousCatalog = catalog
    ? catalogSnapshots
        .filter((row) => row.catalogSnapshotDate < catalog.catalogSnapshotDate)
        .sort((a, b) =>
          b.catalogSnapshotDate.localeCompare(a.catalogSnapshotDate)
        )[0]
    : undefined;
  const catalogChange =
    catalog && previousCatalog
      ? catalog.totals.catalogRecords - previousCatalog.totals.catalogRecords
      : null;
  const expectedDays =
    (new Date(`${window.endExclusive}T00:00:00Z`).getTime() -
      new Date(`${window.start}T00:00:00Z`).getTime()) /
    DAY;
  const dailyComplete =
    new Set(daily.map((row) => row.day)).size === expectedDays;
  const monthly = window.months.map((period) => ({
    period,
    label: monthLabel(period, true),
    sources: periods[period]?.totals.sources ?? null,
    downloads: periods[period]?.totals.downloads ?? null,
  }));
  const total = (field: 'sources' | 'downloads') => {
    const counts = monthly.map((row) => row[field]);
    return counts.every((count) => count !== null)
      ? counts.reduce((sum, count) => sum + count, 0)
      : null;
  };
  return {
    recordAccessPatterns: rankedSearches
      ? resourceAccessPatterns(rankedSearches.resources)
      : null,
    catalog: catalog
      ? {
          total: catalog.totals.catalogRecords,
          date: catalog.catalogSnapshotDate,
          previousTotal: previousCatalog?.totals.catalogRecords ?? null,
          previousDate: previousCatalog?.catalogSnapshotDate ?? null,
          change: catalogChange,
          percentChange:
            catalogChange !== null &&
            previousCatalog &&
            previousCatalog.totals.catalogRecords > 0
              ? (catalogChange / previousCatalog.totals.catalogRecords) * 100
              : null,
        }
      : null,
    window,
    daily,
    monthly,
    searches: dailyComplete
      ? daily.reduce((sum, row) => sum + row.searches, 0)
      : null,
    views: dailyComplete
      ? daily.reduce((sum, row) => sum + row.views, 0)
      : null,
    // Use a period-wide distinct count; daily visit estimates cannot be added.
    visits: rankedOutcomes?.audience.trackedVisits ?? null,
    estimatedVisits: window.months.some((period) => {
      const audience = periods[period]?.audience;
      return audience && 'estimated' in audience && audience.estimated === true;
    }),
    dailyComplete,
    sources: total('sources'),
    downloads: total('downloads'),
    queries:
      rankedSearches?.queries ??
      (selection === 'month'
        ? (snapshot?.topSearches.queries ?? historicalSearches?.queries ?? null)
        : null),
    zeroQueries:
      rankedSearches?.zeroQueries ??
      (selection === 'month'
        ? (snapshot?.searchSnapshot.zeroQueries ??
          historicalZero?.zeroQueries ??
          null)
        : null),
    outlinks: rankedOutcomes?.outlinks ?? null,
    topDownloads: rankedOutcomes?.downloads ?? null,
  };
}

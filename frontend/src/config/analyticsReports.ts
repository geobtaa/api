import { latestMonth, monthLabel, comparisonLabel } from './analyticsPeriods';
export const analyticsReports = [
  {
    id: 'overview',
    label: 'Overview',
    period: monthLabel(latestMonth),
    description:
      'Monthly highlights, daily interactions, searches, and traffic peaks.',
  },
  {
    id: 'comparison',
    label: 'Month comparison',
    period: comparisonLabel,
    description: 'Compare portal totals and daily trends.',
  },
  {
    id: 'content',
    label: 'Popular content',
    period: monthLabel(latestMonth),
    description:
      'Explore leading resources, collections, and download activity.',
  },
  {
    id: 'discovery',
    label: 'Searches',
    period: monthLabel(latestMonth),
    description:
      'Understand search terms, filters, and searches without results.',
  },
  {
    id: 'members',
    label: 'Members',
    period: monthLabel(latestMonth),
    description:
      'Review alliance contributions or focus on an individual campus.',
  },
  {
    id: 'clients',
    label: 'Clients & API keys',
    period: monthLabel(latestMonth),
    description:
      'Explore declared clients, API key attribution, and MCP and GIS request signals.',
  },
  {
    id: 'platform',
    label: 'API reliability',
    period: monthLabel(latestMonth),
    description:
      'Inspect request traffic, response times, and service reliability.',
  },
] as const;

export type AnalyticsReport = (typeof analyticsReports)[number]['id'];

export function analyticsReportHref(
  report: AnalyticsReport,
  month?: string | null
) {
  const params = new URLSearchParams();
  const path =
    report === 'overview'
      ? '/analytics'
      : `/analytics/${report === 'discovery' ? 'searches' : report}`;
  if (month && /^(?:\d{4}-(?:0[1-9]|1[0-2])|ay-\d{4}|all)$/.test(month))
    params.set('month', month);
  return `${path}${params.size ? `?${params}` : ''}`;
}

export function analyticsMonth(params: URLSearchParams) {
  return monthLabel(
    params.get('month') === 'all'
      ? latestMonth
      : params.get('month') || latestMonth
  ).replace(/ \d{4}$/, '');
}

export function selectedAnalyticsReport(
  params: URLSearchParams,
  pathname?: string
) {
  // Preserve existing Daily activity links as aliases for the merged overview.
  const requested = pathname?.split('/')[2] || params.get('report');
  const reportId =
    requested === 'activity'
      ? 'overview'
      : requested === 'searches'
        ? 'discovery'
        : requested;
  const report =
    analyticsReports.find((entry) => entry.id === reportId) ??
    analyticsReports[0];
  return report.id === 'comparison'
    ? report
    : {
        ...report,
        period:
          params.get('month') === 'all'
            ? 'All time'
            : monthLabel(params.get('month') || latestMonth),
      };
}

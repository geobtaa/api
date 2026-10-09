export const analyticsReports = [
  {
    id: 'overview',
    label: 'Overview',
    period: 'September 2026',
    description:
      'Monthly highlights, daily interactions, searches, and traffic peaks.',
  },
  {
    id: 'comparison',
    label: 'Month comparison',
    period: 'July–September 2026',
    description: 'Compare portal totals and daily trends.',
  },
  {
    id: 'content',
    label: 'Popular content',
    period: 'September 2026',
    description:
      'Explore leading resources, collections, and download activity.',
  },
  {
    id: 'discovery',
    label: 'Searches',
    period: 'September 2026',
    description:
      'Understand search terms, filters, and searches without results.',
  },
  {
    id: 'members',
    label: 'Members',
    period: 'September 2026',
    description:
      'Review alliance contributions or focus on an individual campus.',
  },
  {
    id: 'clients',
    label: 'Clients & API keys',
    period: 'September 2026',
    description:
      'Explore declared clients, API key attribution, and MCP and GIS request signals.',
  },
  {
    id: 'platform',
    label: 'API reliability',
    period: 'September 2026',
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
  if (report !== 'overview') params.set('report', report);
  if (month && /^(?:\d{4}-(?:0[1-9]|1[0-2])|ay-\d{4}|all)$/.test(month))
    params.set('month', month);
  return `/analytics${params.size ? `?${params}` : ''}`;
}

export function analyticsMonth(params: URLSearchParams) {
  return params.get('month') === '2026-07' ? 'July' : 'August';
}

export function selectedAnalyticsReport(params: URLSearchParams) {
  // Preserve existing Daily activity links as aliases for the merged overview.
  const reportId =
    params.get('report') === 'activity' ? 'overview' : params.get('report');
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
            : params.get('month') === '2026-07'
              ? 'July 2026'
              : params.get('month') === '2026-08'
                ? 'August 2026'
                : 'September 2026',
      };
}

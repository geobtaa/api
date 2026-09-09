export const analyticsReports = [
  {
    id: 'overview',
    label: 'Overview',
    period: 'August 2026',
    description: 'Latest monthly highlights and a guide to the reports.',
  },
  {
    id: 'comparison',
    label: 'Month comparison',
    period: 'July–August 2026',
    description:
      'Compare portal totals, daily trends, and member activity. Export figures for reporting.',
  },
  {
    id: 'content',
    label: 'Popular content',
    period: 'July 2026',
    description:
      'Explore leading resources, collections, and download activity.',
  },
  {
    id: 'members',
    label: 'Members',
    period: 'July 2026',
    description:
      'Review alliance contributions or focus on an individual campus.',
  },
  {
    id: 'activity',
    label: 'Daily activity',
    period: 'July 2026',
    description: 'Follow daily interactions, searches, and traffic peaks.',
  },
  {
    id: 'discovery',
    label: 'Discovery',
    period: 'July 2026',
    description:
      'Understand search terms, filters, and searches without results.',
  },
  {
    id: 'platform',
    label: 'API reliability',
    period: 'July 2026',
    description:
      'Inspect request traffic, response times, and service reliability.',
  },
] as const;

export type AnalyticsReport = (typeof analyticsReports)[number]['id'];

export function analyticsReportHref(report: AnalyticsReport) {
  return report === 'overview' ? '/analytics' : `/analytics?report=${report}`;
}

/* eslint-disable react-refresh/only-export-components */
import type { LoaderFunctionArgs, MetaFunction } from 'react-router';
import { analyticsReports } from '../../src/config/analyticsReports';
import { AnalyticsPage } from '../../src/pages/AnalyticsPage';
import { buildSeoMeta } from '../../src/config/seo';

const description =
  'Compare July and August 2026 API traffic and discovery activity, with detailed July resource, collection, and member reports.';

export function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const report =
    analyticsReports.find(
      (entry) => entry.id === url.searchParams.get('report')
    ) ?? analyticsReports[0];
  return { currentUrl: url.href, report };
}

export const meta: MetaFunction<typeof loader> = ({ data }) =>
  buildSeoMeta({
    title: `${data?.report.label ?? 'Overview'} — Analytics — ${data?.report.period ?? 'August 2026'}`,
    description,
    url: data?.currentUrl,
  });

export default function Analytics() {
  return <AnalyticsPage />;
}

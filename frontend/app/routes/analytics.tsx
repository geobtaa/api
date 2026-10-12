/* eslint-disable react-refresh/only-export-components */
import {
  useSearchParams,
  redirect,
  type LoaderFunctionArgs,
  type MetaFunction,
} from 'react-router';
import { RuntimeAnalyticsPage } from '../../src/components/analytics/RuntimeAnalyticsPage';
import {
  analyticsReports,
  analyticsReportHref,
  selectedAnalyticsReport,
} from '../../src/config/analyticsReports';
import { AnalyticsPage } from '../../src/pages/AnalyticsPage';
import { buildSeoMeta } from '../../src/config/seo';

const description =
  'API traffic and discovery reporting by month, academic year, and all time.';

export function loader({ request, params }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const pathReport = params.report;
  if (
    pathReport &&
    pathReport !== 'activity' &&
    !analyticsReports.some((r) => r.id === pathReport)
  ) {
    throw new Response('Analytics report not found', { status: 404 });
  }
  const report = selectedAnalyticsReport(url.searchParams, url.pathname);
  const canonicalPath = analyticsReportHref(report.id);
  if (url.searchParams.has('report') || url.pathname !== canonicalPath) {
    url.searchParams.delete('report');
    return redirect(`${canonicalPath}${url.search}${url.hash}`, 301);
  }
  return { currentUrl: url.href, report };
}

export const meta: MetaFunction<typeof loader> = ({ data }) =>
  buildSeoMeta({
    title: `${data?.report.label ?? 'Overview'} — API Analytics`,
    description,
    url: data?.currentUrl,
  });

export default function Analytics() {
  const [params] = useSearchParams();
  return params.get('runtime') === '1' ||
    import.meta.env.VITE_ANALYTICS_RUNTIME === 'true' ? (
    <RuntimeAnalyticsPage />
  ) : (
    <AnalyticsPage />
  );
}

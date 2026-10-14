import { AnalyticsDataContext } from '../../src/components/analytics/AnalyticsData';
import { analyticsSnapshot } from '../lib/analytics-data.server';
import {
  analyticsHeaders,
  requireAnalyticsSession,
} from '../lib/analytics-auth.server';
/* eslint-disable react-refresh/only-export-components */
import {
  useSearchParams,
  useLoaderData,
  data,
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

export const headers = () => analyticsHeaders;

export async function loader({ request, params }: LoaderFunctionArgs) {
  await requireAnalyticsSession(request);
  const url = new URL(request.url);
  const pathReport = params.report;
  if (
    pathReport &&
    pathReport !== 'activity' &&
    pathReport !== 'searches' &&
    !analyticsReports.some((r) => r.id === pathReport)
  ) {
    throw new Response('Analytics report not found', {
      status: 404,
      headers: analyticsHeaders,
    });
  }
  const report = selectedAnalyticsReport(url.searchParams, url.pathname);
  const canonicalPath = analyticsReportHref(report.id);
  if (url.searchParams.has('report') || url.pathname !== canonicalPath) {
    url.searchParams.delete('report');
    return redirect(`${canonicalPath}${url.search}${url.hash}`, {
      status: 301,
      headers: analyticsHeaders,
    });
  }
  return data(
    { currentUrl: url.href, report, snapshot: analyticsSnapshot },
    { headers: analyticsHeaders }
  );
}

export const meta: MetaFunction<typeof loader> = ({ data }) =>
  buildSeoMeta({
    title: `${data?.report.label ?? 'Overview'} — API Analytics`,
    description,
    url: data?.currentUrl,
  });

export default function Analytics() {
  const [params] = useSearchParams();
  const { snapshot } = useLoaderData<typeof loader>();
  return (
    <AnalyticsDataContext.Provider value={snapshot}>
      {params.get('runtime') === '1' ||
      import.meta.env.VITE_ANALYTICS_RUNTIME === 'true' ? (
        <RuntimeAnalyticsPage />
      ) : (
        <AnalyticsPage />
      )}
    </AnalyticsDataContext.Provider>
  );
}

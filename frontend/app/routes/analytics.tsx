/* eslint-disable react-refresh/only-export-components */
import {
  useSearchParams,
  type LoaderFunctionArgs,
  type MetaFunction,
} from 'react-router';
import { RuntimeAnalyticsPage } from '../../src/components/analytics/RuntimeAnalyticsPage';
import { selectedAnalyticsReport } from '../../src/config/analyticsReports';
import { AnalyticsPage } from '../../src/pages/AnalyticsPage';
import { buildSeoMeta } from '../../src/config/seo';

const description =
  'API traffic and discovery reporting by month, academic year, and all time.';

export function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const report = selectedAnalyticsReport(url.searchParams);
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

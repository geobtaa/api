/* eslint-disable react-refresh/only-export-components */
import type { LoaderFunctionArgs, MetaFunction } from 'react-router';
import { AnalyticsPage } from '../../src/pages/AnalyticsPage';
import { buildSeoMeta } from '../../src/config/seo';

const description =
  'Compare July and August 2026 API traffic and discovery activity, with detailed July resource, collection, and member reports.';

export function loader({ request }: LoaderFunctionArgs) {
  return { currentUrl: new URL(request.url).href };
}

export const meta: MetaFunction<typeof loader> = ({ data }) =>
  buildSeoMeta({
    title: 'Geo Charts — July–August 2026',
    description,
    url: data?.currentUrl,
  });

export default function Analytics() {
  return <AnalyticsPage />;
}

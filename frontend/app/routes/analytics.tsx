/* eslint-disable react-refresh/only-export-components */
import type { LoaderFunctionArgs, MetaFunction } from 'react-router';
import { AnalyticsPage } from '../../src/pages/AnalyticsPage';
import { buildSeoMeta } from '../../src/config/seo';

const description =
  'The July 2026 monthly pulse for discovery, resources, collections, and platform activity across the BTAA Geoportal.';

export function loader({ request }: LoaderFunctionArgs) {
  return { currentUrl: new URL(request.url).href };
}

export const meta: MetaFunction<typeof loader> = ({ data }) =>
  buildSeoMeta({
    title: 'Geo Charts — July 2026',
    description,
    url: data?.currentUrl,
  });

export default function Analytics() {
  return <AnalyticsPage />;
}

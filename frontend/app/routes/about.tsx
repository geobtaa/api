/* eslint-disable react-refresh/only-export-components */
import type { LoaderFunctionArgs, MetaFunction } from 'react-router';
import { AboutPage } from '../../src/pages/AboutPage';
import { buildSeoMeta } from '../../src/config/seo';

export function loader({ request }: LoaderFunctionArgs) {
  return { currentUrl: new URL(request.url).href };
}

export const meta: MetaFunction<typeof loader> = ({ data }) =>
  buildSeoMeta({
    title: 'About',
    description:
      'Learn about the Big Ten Academic Alliance Geoportal and the collections it helps users discover.',
    url: data?.currentUrl,
  });

export default function About() {
  return <AboutPage />;
}

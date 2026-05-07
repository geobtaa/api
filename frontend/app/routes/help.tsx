import type { LoaderFunctionArgs, MetaFunction } from 'react-router';
import { HelpPage } from '../../src/pages/HelpPage';
import { buildSeoMeta } from '../../src/config/seo';

export function loader({ request }: LoaderFunctionArgs) {
  return { currentUrl: new URL(request.url).href };
}

export const meta: MetaFunction<typeof loader> = ({ data }) =>
  buildSeoMeta({
    title: 'Help',
    description:
      'Learn how to search, filter, view resources, and use bookmarks in the Big Ten Academic Alliance Geoportal.',
    url: data?.currentUrl,
  });

export default function Help() {
  return <HelpPage />;
}

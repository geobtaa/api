import { NotFoundPage } from '../../src/pages/NotFoundPage';
import { GeoportalRouteErrorBoundary } from '../../src/pages/ErrorPage';
import { buildSeoMeta } from '../../src/config/seo';

/**
 * Catch-all route for 404 pages.
 */
export default function NotFound() {
  return <NotFoundPage />;
}

export async function loader() {
  throw new Response('Page not found', {
    status: 404,
    statusText: 'Not Found',
  });
}

export function ErrorBoundary() {
  return <GeoportalRouteErrorBoundary />;
}

export function meta() {
  return buildSeoMeta({ title: 'Page Not Found' });
}

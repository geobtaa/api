import { useEffect, useState, type ReactNode } from 'react';
import {
  createBrowserRouter,
  createMemoryRouter,
  RouterProvider,
} from 'react-router';
/** Data-router context supports the analytics header's sign-out Form. */
export function AnalyticsTestRouter({
  children,
  initialEntries,
  browser = false,
}: {
  children: ReactNode;
  initialEntries?: string[];
  browser?: boolean;
}) {
  const [router] = useState(() =>
    browser
      ? createBrowserRouter([{ path: '*', element: children }])
      : createMemoryRouter([{ path: '*', element: children }], {
          initialEntries: initialEntries ?? [
            window.location.pathname + window.location.search,
          ],
        })
  );
  useEffect(() => () => router.dispose(), [router]);
  return <RouterProvider router={router} />;
}

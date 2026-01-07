import { Navigate, useSearchParams } from "react-router";
import { HomePage } from "../../src/pages/HomePage";

/**
 * Root route - redirects to search if there are search params, otherwise shows home page.
 */
export default function Index() {
  const [searchParams] = useSearchParams();
  const hasSearchParams = Array.from(searchParams.entries()).length > 0;

  if (hasSearchParams) {
    const searchString = `?${searchParams.toString()}`;
    return <Navigate to={`/search${searchString}`} replace />;
  }

  return <HomePage />;
}

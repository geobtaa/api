import { NotFoundPage } from "../../src/pages/NotFoundPage";
import { buildSeoMeta } from "../../src/config/seo";

/**
 * Catch-all route for 404 pages.
 */
export default function NotFound() {
  return <NotFoundPage />;
}

export function meta() {
  return buildSeoMeta({ title: "Page Not Found" });
}

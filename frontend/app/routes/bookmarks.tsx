import { BookmarksPage } from "../../src/pages/BookmarksPage";
import { buildSeoMeta } from "../../src/config/seo";

/**
 * Bookmarks page - client-side only (uses cookies for bookmarks).
 */
export default function Bookmarks() {
  return <BookmarksPage />;
}

export function meta() {
  return buildSeoMeta({ title: "Bookmarked Resources", url: "/bookmarks" });
}
